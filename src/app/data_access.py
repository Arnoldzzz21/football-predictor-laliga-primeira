"""
data_access.py
---------------
Capa de lectura para la app: envuelve src/utils/parquet_io.py con cache de
Streamlit y agrega la logica de proyeccion de partido (lambda_home/away,
matriz de marcadores, top-3 resultados mas probables) reutilizando
src/utils/dixon_coles.py.

Nota de estado real del pipeline (2026-09-26): Team_Ratings_Builder corre
hasta la jornada que ya se jugo (incluye la jornada recien cerrada), pero
Match_Predictions_Builder puede quedar un paso atras (todavia no genera la
fila de la proxima jornada). Por eso match_projection() calcula la
proyeccion en vivo con la ultima foto de team_ratings cuando no encuentra
la fila ya guardada en match_predictions -- la app nunca debe quedar sin
proyeccion para la proxima jornada.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.utils.parquet_io import read_partition
from src.utils.dixon_coles import score_matrix, outcome_probs

LAKE_ROOT = Path("data")
ACTIVE_SEASON = "2026-2027"

LEAGUE_LABELS = {"laliga": "LaLiga EA Sports", "primeira_liga": "Primeira Liga"}
LEAGUE_FLAG = {"laliga": "ES", "primeira_liga": "PT"}


@st.cache_data(ttl=3600, show_spinner=False)
def load_teams_master() -> pd.DataFrame:
    return read_partition(LAKE_ROOT / "reference" / "teams_master.parquet").to_pandas()


@st.cache_data(ttl=3600, show_spinner=False)
def load_matches(league: str, season: str = ACTIVE_SEASON) -> pd.DataFrame:
    path = LAKE_ROOT / "silver" / league / f"season={season}" / "matches.parquet"
    return read_partition(path).to_pandas()


@st.cache_data(ttl=3600, show_spinner=False)
def load_team_ratings(league: str, season: str = ACTIVE_SEASON) -> pd.DataFrame:
    path = LAKE_ROOT / "gold" / league / f"season={season}" / "team_ratings.parquet"
    return read_partition(path).to_pandas()


@st.cache_data(ttl=3600, show_spinner=False)
def load_match_predictions(league: str, season: str = ACTIVE_SEASON) -> pd.DataFrame:
    path = LAKE_ROOT / "gold" / league / f"season={season}" / "match_predictions.parquet"
    return read_partition(path).to_pandas()


@st.cache_data(ttl=3600, show_spinner=False)
def load_season_simulations(league: str, season: str = ACTIVE_SEASON) -> pd.DataFrame:
    path = LAKE_ROOT / "gold" / "season_simulations" / league / f"season={season}" / "season_simulations.parquet"
    return read_partition(path).to_pandas()


def team_name_map(teams: pd.DataFrame, league: str) -> dict[str, str]:
    sub = teams[teams.league == league]
    return dict(zip(sub.team_key, sub.official_name))


def active_season_teams(matches: pd.DataFrame) -> list[str]:
    return sorted(pd.unique(matches[["home_team_key", "away_team_key"]].values.ravel()).tolist())


def latest_ratings_snapshot(ratings: pd.DataFrame) -> pd.DataFrame:
    """Una fila por team_key, a la jornada mas reciente disponible."""
    last_md = ratings["matchday"].max()
    return ratings[ratings["matchday"] == last_md].set_index("team_key")


def global_params(ratings_snapshot: pd.DataFrame) -> tuple[float, float, float]:
    row = ratings_snapshot.iloc[0]
    return float(row["mu"]), float(row["gamma"]), float(row["rho"])


def _predict_lambdas(home_key: str, away_key: str, snap: pd.DataFrame,
                      mu: float, gamma: float) -> tuple[float, float]:
    """Misma forma funcional que entrena fit_dixon_coles (dixon_coles.py)."""
    att_h, def_h = snap.loc[home_key, ["attack", "defense"]]
    att_a, def_a = snap.loc[away_key, ["attack", "defense"]]
    lh = float(np.exp(mu + gamma + att_h - def_a))
    la = float(np.exp(mu + att_a - def_h))
    return lh, la


def match_projection(home_key: str, away_key: str, matchday: int,
                      predictions: pd.DataFrame, ratings_snapshot: pd.DataFrame,
                      mu: float, gamma: float, rho: float) -> dict:
    row = predictions[
        (predictions.matchday == matchday)
        & (predictions.home_team_key == home_key)
        & (predictions.away_team_key == away_key)
    ]
    if not row.empty:
        r = row.iloc[0]
        lh, la = float(r.lambda_home), float(r.lambda_away)
        p_home, p_draw, p_away = float(r.p_home), float(r.p_draw), float(r.p_away)
        live = False
    else:
        lh, la = _predict_lambdas(home_key, away_key, ratings_snapshot, mu, gamma)
        p_home, p_draw, p_away = outcome_probs(lh, la, rho)
        live = True

    matrix = score_matrix(lh, la, rho)
    order = np.argsort(matrix.ravel())[::-1][:3]
    top = []
    for flat_idx in order:
        i, j = divmod(int(flat_idx), matrix.shape[1])
        top.append({"home": i, "away": j, "prob": float(matrix[i, j])})

    return {
        "lambda_home": lh, "lambda_away": la,
        "p_home": p_home, "p_draw": p_draw, "p_away": p_away,
        "projected_home": top[0]["home"], "projected_away": top[0]["away"],
        "top_scorelines": top,
        "live_projection": live,
    }


def scoreline_accuracy(proj_h: int, proj_a: int, final_h: int, final_a: int,
                        penalty_per_goal: float = 20.0) -> float:
    """Que tan cerca estuvo el marcador exacto proyectado (proj_h-proj_a) del
    resultado final (final_h-final_a) -- el badge que se muestra junto al
    resultado final en la app. 100% si el marcador coincide exacto; baja
    `penalty_per_goal` puntos porcentuales por cada gol de diferencia total
    (|home| + |away|), sin bajar de 0. Con el default de 20 pts/gol: mismo
    marcador -> 100%, un gol de diferencia -> 80%, dos -> 60%, etc."""
    diff = abs(proj_h - final_h) + abs(proj_a - final_a)
    return max(0.0, 100.0 - penalty_per_goal * diff)


DRAW_MARGIN = 0.06


def predicted_outcome(p_home: float, p_draw: float, p_away: float,
                       draw_margin: float = DRAW_MARGIN) -> str:
    """Etiqueta 1X2 que el modelo 'apuesta' para un partido, dadas sus 3
    probabilidades. Con argmax() puro el empate practicamente nunca gana
    (es el resultado "del medio" entre dos alternativas mas extremas): en
    el historial completo (4 temporadas, ambas ligas, 2158 partidos jugados)
    el modelo elegia Draw como resultado mas probable en apenas 0.5% de los
    casos, contra un 26% de empates reales.

    Este ajuste le da al empate una oportunidad justa: si p_draw esta a
    menos de `draw_margin` puntos porcentuales de la probabilidad mas alta
    entre local/visita, se predice Draw. Medido contra el mismo historial,
    esto es un trade-off honesto, no una mejora gratis: con margin=0.06 la
    precision 1X2 baja ~0.6pp (53.0% -> 52.4%) pero el modelo pasa de
    "casi nunca" a "a veces" predecir empate (0.5% -> 5.2% de los partidos,
    y de los empates reales que efectivamente detecta, de 0.4% a 6.1%) --
    una version que nunca dice Draw se ve poco creible aunque tecnicamente
    argmax puro maximice el % de acierto bruto."""
    best_side = "H" if p_home >= p_away else "A"
    best_side_p = max(p_home, p_away)
    if p_draw >= best_side_p - draw_margin:
        return "D"
    return best_side


def matchday_brier_score(matches: pd.DataFrame, predictions: pd.DataFrame,
                          team_key: str | None = None) -> float | None:
    """Brier score promedio (0 a 0.667, mientras mas bajo mejor) sobre las
    jornadas ya jugadas: mide que tan bien calibradas estan las 3
    probabilidades completas, no solo si se acerto el resultado mas
    probable -- por eso complementa (no reemplaza) la precision 1X2 de
    matchday_accuracy_trend()."""
    finished = matches[matches.status == "FINISHED"].copy()
    if team_key:
        finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
    merged = finished.merge(
        predictions[["matchday", "home_team_key", "away_team_key", "p_home", "p_draw", "p_away"]],
        on=["matchday", "home_team_key", "away_team_key"], how="inner",
    )
    if merged.empty:
        return None
    probs = merged[["p_home", "p_draw", "p_away"]].to_numpy()
    y = merged["result"].map({"H": 0, "D": 1, "A": 2}).to_numpy()
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(probs)), y] = 1
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


def matchday_status(matches: pd.DataFrame) -> tuple[int | None, int | None]:
    """(ultima jornada jugada, proxima jornada) para esta liga/temporada."""
    finished = matches[matches.status == "FINISHED"]
    last_finished = int(finished.matchday.max()) if not finished.empty else None
    upcoming_candidates = sorted(matches[matches.matchday > (last_finished or 0)].matchday.unique())
    next_md = int(upcoming_candidates[0]) if upcoming_candidates else None
    return last_finished, next_md


def matchday_accuracy_trend(matches: pd.DataFrame, predictions: pd.DataFrame,
                             team_key: str | None = None) -> tuple[list[int], list[float]]:
    """% de aciertos 1X2 por jornada jugada, comparando el resultado
    proyectado (predicted_outcome(), argmax + margen para el empate --
    ver esa funcion) contra el resultado real."""
    finished = matches[matches.status == "FINISHED"].copy()
    if team_key:
        finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
    merged = finished.merge(
        predictions[["matchday", "home_team_key", "away_team_key", "p_home", "p_draw", "p_away"]],
        on=["matchday", "home_team_key", "away_team_key"], how="inner",
    )
    if merged.empty:
        return [], []
    pred_label = merged.apply(
        lambda r: predicted_outcome(r.p_home, r.p_draw, r.p_away), axis=1
    )
    merged["hit"] = (pred_label == merged["result"]).astype(int)
    by_md = merged.groupby("matchday")["hit"].mean().sort_index()
    return by_md.index.tolist(), (by_md.values * 100).tolist()
