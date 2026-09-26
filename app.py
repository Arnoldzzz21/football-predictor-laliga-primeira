"""
app.py
------
Football Predictor -- LaLiga EA Sports & Primeira Liga (temporada 2026-2027)
Entry point de la app en Streamlit. Corre con:

    streamlit run app.py

desde la raiz del proyecto (usa rutas relativas a data/ igual que el resto
del pipeline).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.app import theme, components as C
from src.app.data_access import (
    LEAGUE_LABELS, LEAGUE_FLAG,
    load_teams_master, load_matches, load_team_ratings,
    load_match_predictions, load_season_simulations,
    team_name_map, active_season_teams,
    latest_ratings_snapshot, global_params, match_projection,
    matchday_status, matchday_accuracy_trend,
)

st.set_page_config(page_title="Football Predictor", page_icon="⚽", layout="wide")
theme.inject()

# ---------------------------------------------------------------- Header --
teams_master = load_teams_master()

top_l, top_r = st.columns([3, 2])
with top_l:
    st.markdown(
        '<div class="mono" style="font-size:24px; font-weight:700;">Football Predictor</div>'
        '<div style="font-size:13px; color:#8892B0;">LaLiga EA Sports · Primeira Liga — Temporada 2026-2027</div>',
        unsafe_allow_html=True,
    )
with top_r:
    c1, c2 = st.columns(2)
    league = c1.radio("Liga", options=list(LEAGUE_LABELS.keys()),
                       format_func=lambda k: LEAGUE_LABELS[k], horizontal=True,
                       label_visibility="collapsed")

matches = load_matches(league)
ratings = load_team_ratings(league)
predictions = load_match_predictions(league)
simulations = load_season_simulations(league)
name_of = team_name_map(teams_master, league)
iso2 = LEAGUE_FLAG[league]

team_options = ["Todos"] + active_season_teams(matches)
with top_r:
    team_filter = c2.selectbox(
        "Equipo", options=team_options,
        format_func=lambda k: "Equipo: Todos" if k == "Todos" else name_of.get(k, k),
        label_visibility="collapsed",
    )
team_key = None if team_filter == "Todos" else team_filter

st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)

snap = latest_ratings_snapshot(ratings)
mu, gamma, rho = global_params(snap)
last_md, next_md = matchday_status(matches)


def _matches_for(md: int) -> pd.DataFrame:
    df = matches[matches.matchday == md]
    if team_key:
        df = df[(df.home_team_key == team_key) | (df.away_team_key == team_key)]
    return df


# --------------------------------------------------------- Jornada jugada --
if last_md is not None:
    played = _matches_for(last_md)
    st.markdown(f"##### Jornada {last_md} · {LEAGUE_LABELS[league]} — Jugada")
    st.caption("Proyección pre-partido vs. resultado real")
    for _, m in played.iterrows():
        proj = match_projection(m.home_team_key, m.away_team_key, last_md,
                                 predictions, snap, mu, gamma, rho)
        st.markdown(
            C.played_match_row(
                name_of.get(m.home_team_key, m.home_team_key),
                name_of.get(m.away_team_key, m.away_team_key),
                iso2,
                proj["projected_home"], proj["projected_away"],
                int(m.home_score), int(m.away_score),
                last_md,
            ),
            unsafe_allow_html=True,
        )

# ------------------------------------------------------- Jornada próxima --
if next_md is not None:
    upcoming = _matches_for(next_md)
    st.markdown(f"##### Jornada {next_md} · {LEAGUE_LABELS[league]} — Próxima")
    for _, m in upcoming.iterrows():
        proj = match_projection(m.home_team_key, m.away_team_key, next_md,
                                 predictions, snap, mu, gamma, rho)
        st.markdown(
            C.upcoming_match_card(
                name_of.get(m.home_team_key, m.home_team_key),
                name_of.get(m.away_team_key, m.away_team_key),
                iso2,
                proj["projected_home"], proj["projected_away"],
                proj["p_home"], proj["p_draw"], proj["p_away"],
                proj["top_scorelines"], next_md, proj["live_projection"],
            ),
            unsafe_allow_html=True,
        )
    heat_home, heat_away = upcoming.iloc[0].home_team_key, upcoming.iloc[0].away_team_key
else:
    heat_home = heat_away = None

if last_md is None and next_md is None:
    st.info("No hay partidos cargados todavía para esta liga/temporada.")

# ------------------------------------------------------------ Estadísticas --
st.markdown("##### Estadísticas del modelo")
col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

with col1:
    st.markdown('<div class="fp-card">', unsafe_allow_html=True)
    st.markdown('<span style="font-size:12px; color:#8892B0;">Precisión 1X2 por jornada</span>', unsafe_allow_html=True)
    mds, acc = matchday_accuracy_trend(matches, predictions, team_key)
    st.markdown(C.accuracy_trend_svg(mds, acc), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="fp-card">', unsafe_allow_html=True)
    st.markdown('<span style="font-size:12px; color:#8892B0;">Rendimiento del modelo</span>', unsafe_allow_html=True)
    overall_acc = np.mean(acc) if acc else 0.0
    n_sims = int(simulations.n_simulations.iloc[0]) if not simulations.empty else 0
    kpi_values = [overall_acc, overall_acc * 0.4, float(snap["attack"].std()), n_sims / 100]
    kpi_labels = [f"{overall_acc:.0f}%", "marcador exacto ↓", f"σ ataque {snap['attack'].std():.2f}", f"{n_sims:,} sims"]
    st.markdown(C.kpi_bars(kpi_values, kpi_labels), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="fp-card">', unsafe_allow_html=True)
    st.markdown('<span style="font-size:12px; color:#8892B0;">Mapa de calor — intensidad ofensiva proyectada</span>', unsafe_allow_html=True)
    if heat_home is not None:
        atk_min, atk_max = snap["attack"].min(), snap["attack"].max()
        span = (atk_max - atk_min) or 1.0
        h_int = float((snap.loc[heat_home, "attack"] - atk_min) / span)
        a_int = float((snap.loc[heat_away, "attack"] - atk_min) / span)
        st.markdown(
            C.heat_pitch_svg(name_of.get(heat_home, heat_home), name_of.get(heat_away, heat_away), h_int, a_int),
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div style="font-size:12px; color:#8892B0;">Sin próxima jornada para proyectar.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="fp-card">', unsafe_allow_html=True)
    st.markdown('<span style="font-size:12px; color:#8892B0;">Tabla proyectada (Top 4)</span>', unsafe_allow_html=True)
    top4 = simulations.sort_values("avg_position").head(4).copy()
    rows = [
        {"pos": i + 1, "name": name_of.get(r.team_key, r.team_key),
         "avg_position": r.avg_position, "prob_champions_league": r.prob_champions_league}
        for i, r in enumerate(top4.itertuples())
    ]
    st.markdown(C.top_table_html(rows), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
