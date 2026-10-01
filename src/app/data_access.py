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

# De momento la app solo expone la temporada activa en el slicer de Season
# -- el Data Lake ya tiene Silver/Gold de 3 temporadas anteriores (usadas
# como historico para entrenar el modelo), pero season_simulations (Monte
# Carlo) solo existe para la temporada activa, asi que navegar temporadas
# pasadas desde la UI dejaria la tabla proyectada rota. Cuando arranque
# 2027-2028 esta lista pasa a tener 2 elementos y el slicer queda listo
# para eso sin mas cambios.
AVAILABLE_SEASONS = [ACTIVE_SEASON]

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


# "Clear favorite" threshold for showing a bigger scoreline in UPCOMING
# matches. Set with a backtest on the full history (2,158 matches, both
# leagues, 4 seasons): with P(favorite wins) >= 0.65 it applies to ~15% of
# matches, and in those the favorite won 82% of the time and by 2+ goals 57%.
BLOWOUT_MIN_FAV_PROB = 0.65


def blowout_scoreline(lh: float, la: float, p_home: float,
                       p_away: float) -> tuple[int, int] | None:
    """Blowout scoreline for a clear favorite, or None if the match is
    close (in that case the usual most likely scoreline is kept).

    Rule: favorite goals = floor(lambda_fav + 0.75) (its expected goals
    rounded with an upward bias) and opponent goals = floor(lambda_opp).
    This is not the single most likely scoreline (that is usually 2-0), but
    in the backtest on clear-favorite matches it scores equal or better
    than the most likely scoreline: average accuracy badge 64.2 vs 63.0,
    exact score 14.4% vs 12.5%, and lower total-goal error (1.41 vs 1.64).
    It overestimates the real average margin (2.6 vs 1.9 goals), in
    exchange for better reflecting how much the favorite scores.

    Returns the scoreline as (home, away)."""
    fav_is_home = p_home >= p_away
    if max(p_home, p_away) < BLOWOUT_MIN_FAV_PROB:
        return None
    lam_fav, lam_dog = (lh, la) if fav_is_home else (la, lh)
    fav_goals = int(np.floor(lam_fav + 0.75))
    dog_goals = int(np.floor(lam_dog))
    if fav_goals - dog_goals < 1:  # safeguard: never show a draw/loss for the favorite
        return None
    return (fav_goals, dog_goals) if fav_is_home else (dog_goals, fav_goals)


def match_projection(home_key: str, away_key: str, matchday: int,
                      predictions: pd.DataFrame, ratings_snapshot: pd.DataFrame,
                      mu: float, gamma: float, rho: float,
                      show_blowout: bool = False) -> dict:
    """show_blowout=True ONLY for upcoming matches: if the favorite is
    clearly superior, 'projected_home/away' becomes the blowout scoreline
    (blowout_scoreline). Already-played matches always use the original
    most likely scoreline, so their historical results and accuracy badge
    stay exactly the same. The original most likely scoreline is always
    kept in 'modal_home/modal_away'."""
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

    modal_h, modal_a = top[0]["home"], top[0]["away"]
    proj_h, proj_a = modal_h, modal_a
    blowout = blowout_scoreline(lh, la, p_home, p_away) if show_blowout else None
    if blowout is not None:
        proj_h, proj_a = blowout

    return {
        "lambda_home": lh, "lambda_away": la,
        "p_home": p_home, "p_draw": p_draw, "p_away": p_away,
        "projected_home": proj_h, "projected_away": proj_a,
        "modal_home": modal_h, "modal_away": modal_a,
        "is_blowout": blowout is not None,
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


def matchday_rps_score(matches: pd.DataFrame, predictions: pd.DataFrame,
                        team_key: str | None = None) -> float | None:
    """Ranked Probability Score promedio (0 a 1, mientras mas bajo mejor)
    sobre las jornadas ya jugadas. A diferencia del Brier score (que trata
    Home/Draw/Away como categorias sin relacion entre si), RPS respeta el
    orden natural de los 3 resultados -- Home, luego Draw, luego Away, de
    mas a menos favorable al equipo local -- y penaliza menos un pronostico
    que dijo Home y salio Draw que uno que dijo Home y salio Away. Es el
    estandar de facto en la literatura academica de forecasting de futbol
    (Constantinou & Fenton), por eso reemplaza al Brier score generico como
    la metrica de calibracion mostrada en la app.

    Formula (Epstein 1969, r=3 categorias en el orden H-D-A):
    RPS = 1/(r-1) * sum_{i=1}^{r-1} (CumForecast_i - CumActual_i)^2
    El ultimo termino acumulado (i=r) siempre es 0 (forecast y actual suman
    1) por lo que se omite -- no cambia el resultado, solo evita sumar un
    termino que siempre es cero."""
    finished = matches[matches.status == "FINISHED"].copy()
    if team_key:
        finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
    merged = finished.merge(
        predictions[["matchday", "home_team_key", "away_team_key", "p_home", "p_draw", "p_away"]],
        on=["matchday", "home_team_key", "away_team_key"], how="inner",
    )
    if merged.empty:
        return None
    cum_forecast_1 = merged["p_home"]
    cum_forecast_2 = merged["p_home"] + merged["p_draw"]
    is_home = (merged["result"] == "H").astype(float)
    is_draw = (merged["result"] == "D").astype(float)
    cum_actual_1 = is_home
    cum_actual_2 = is_home + is_draw
    rps = 0.5 * ((cum_forecast_1 - cum_actual_1) ** 2 + (cum_forecast_2 - cum_actual_2) ** 2)
    return float(rps.mean())


def avg_goal_error(matches: pd.DataFrame, predictions: pd.DataFrame,
                    team_key: str | None = None) -> float | None:
    """Error promedio de goles totales proyectados vs. el resultado real,
    sobre las jornadas ya jugadas -- complementa a RPS (calibracion de las 3
    probabilidades) con una lectura en goles, mas facil de interpretar para
    quien no trabaja con modelos de probabilidad: "en promedio, el modelo se
    equivoca por X goles en total por partido".

    El marcador proyectado se aproxima redondeando lambda_home/lambda_away
    (el gol esperado de cada equipo) en vez de recalcular la matriz de
    marcadores completa con la correccion Dixon-Coles de goles bajos (rho) --
    misma idea de fondo que scoreline_accuracy() pero sin necesitar rho por
    jornada, una diferencia minima para una metrica agregada de temporada."""
    finished = matches[matches.status == "FINISHED"].copy()
    if team_key:
        finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
    merged = finished.merge(
        predictions[["matchday", "home_team_key", "away_team_key", "lambda_home", "lambda_away"]],
        on=["matchday", "home_team_key", "away_team_key"], how="inner",
    )
    if merged.empty:
        return None
    proj_total = merged["lambda_home"].round() + merged["lambda_away"].round()
    real_total = merged["home_score"] + merged["away_score"]
    return float((proj_total - real_total).abs().mean())


def avg_real_goals(stats_matches: pd.DataFrame, all_matches: pd.DataFrame,
                    team_key: str | None = None) -> tuple[float | None, bool]:
    """Promedio de goles REALES anotados por partido -- reemplaza al viejo
    uso de avg_goal_error() en la tarjeta 'Avg goals', que en realidad
    mostraba el error de proyeccion del modelo (|goles proyectados - goles
    reales|), no un promedio de goles. Esta funcion sí devuelve el
    promedio de goles anotados de verdad.

    stats_matches: partidos de la jornada seleccionada en el filtro
    MATCHDAY. Si ya tiene partidos FINISHED, el promedio se calcula solo
    sobre esa jornada.

    all_matches: todos los partidos de la liga/temporada actual (ya
    filtrados por liga desde app.py via load_matches). Sirve de fallback
    cuando la jornada seleccionada todavia no se jugo -- en vez de "n/a",
    la tarjeta muestra el promedio de goles de la temporada hasta la
    fecha ("las jornadas que no se han jugado aprenden de las que ya se
    jugaron"), siempre dentro de la misma liga para no mezclar el ritmo de
    gol de LaLiga con el de Primeira Liga.

    Devuelve (valor, es_promedio_de_temporada) para que quien llama pueda
    ajustar la etiqueta segun si el numero es de la jornada exacta o del
    fallback de temporada."""
    def _avg(df: pd.DataFrame) -> float | None:
        finished = df[df.status == "FINISHED"]
        if team_key:
            finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
        if finished.empty:
            return None
        return float((finished.home_score + finished.away_score).mean())

    md_avg = _avg(stats_matches)
    if md_avg is not None:
        return md_avg, False
    return _avg(all_matches), True


def avg_prob_on_actual(matches: pd.DataFrame, predictions: pd.DataFrame,
                        team_key: str | None = None) -> float | None:
    """Probabilidad promedio (0-100%, mientras mas alto mejor) que el modelo
    le dio al resultado que realmente ocurrio, sobre las jornadas jugadas.
    Complementa al acierto 1X2 (binario: acerto o no el resultado MAS
    probable) con que tan "convencido" estaba el modelo del resultado
    correcto en promedio -- por ejemplo, un empate que el modelo daba al
    35% (sin ser su favorito) cuenta distinto aca que uno al 5%, aunque
    ambos casos sean un fallo en la metrica de acierto binario."""
    finished = matches[matches.status == "FINISHED"].copy()
    if team_key:
        finished = finished[(finished.home_team_key == team_key) | (finished.away_team_key == team_key)]
    merged = finished.merge(
        predictions[["matchday", "home_team_key", "away_team_key", "p_home", "p_draw", "p_away"]],
        on=["matchday", "home_team_key", "away_team_key"], how="inner",
    )
    if merged.empty:
        return None
    prob_map = {"H": "p_home", "D": "p_draw", "A": "p_away"}
    prob_actual = merged.apply(lambda r: r[prob_map[r["result"]]], axis=1)
    return float(prob_actual.mean() * 100)


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
