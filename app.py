"""
app.py
------
Football Predictor -- LaLiga EA Sports & Primeira Liga (temporada 2026-2027)
Entry point de la app en Streamlit. Corre con:

    streamlit run app.py

desde la raiz del proyecto (usa rutas relativas a data/ igual que el resto
del pipeline). Todo el texto visible en la UI va en ingles; los comentarios
del codigo se quedan en espanol.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.app import theme, components as C
from src.app.theme import ACCENT_LIGHT, GREEN, RED
from src.app.data_access import (
    LEAGUE_LABELS, LEAGUE_FLAG,
    load_teams_master, load_matches, load_team_ratings,
    load_match_predictions, load_season_simulations,
    team_name_map, active_season_teams,
    latest_ratings_snapshot, global_params, match_projection,
    matchday_status, matchday_accuracy_trend, outcome_confidence,
)

st.set_page_config(page_title="Football Predictor", page_icon="⚽", layout="wide")
theme.inject()


def _filter_label(text: str, color: str) -> None:
    st.markdown(
        f'<span style="font-size:11px; font-weight:700; letter-spacing:0.06em; '
        f'color:{color};">{text}</span>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- Header --
teams_master = load_teams_master()

st.markdown(
    '<div class="mono" style="font-size:24px; font-weight:700;">Football Predictor</div>'
    '<div style="font-size:13px; color:#8892B0; margin-bottom:18px;">'
    'LaLiga EA Sports · Primeira Liga — 2026-2027 Season</div>',
    unsafe_allow_html=True,
)

# ------------------------------------------------------------- Filtros --
# Las 3 tarjetas se llenan en orden de dependencia (liga -> datos de esa
# liga -> equipo/jornada), pero cada `with` coloca su contenido en la
# columna que le corresponde sin importar el orden de ejecucion.
f_league, f_team, f_md = st.columns(3)

with f_league:
    with st.container(border=True):
        _filter_label("LEAGUE", ACCENT_LIGHT)
        league = st.selectbox(
            "League", options=list(LEAGUE_LABELS.keys()),
            format_func=lambda k: LEAGUE_LABELS[k], label_visibility="collapsed",
        )

matches = load_matches(league)
ratings = load_team_ratings(league)
predictions = load_match_predictions(league)
simulations = load_season_simulations(league)
name_of = team_name_map(teams_master, league)
iso2 = LEAGUE_FLAG[league]

team_options = ["All"] + active_season_teams(matches)
all_mds = sorted(matches.matchday.unique().tolist())
snap = latest_ratings_snapshot(ratings)
mu, gamma, rho = global_params(snap)
last_md, next_md = matchday_status(matches)
default_md = last_md if last_md in all_mds else (all_mds[0] if all_mds else None)

with f_team:
    with st.container(border=True):
        _filter_label("TEAM", GREEN)
        team_filter = st.selectbox(
            "Team", options=team_options,
            format_func=lambda k: "Team: All" if k == "All" else name_of.get(k, k),
            label_visibility="collapsed",
        )
team_key = None if team_filter == "All" else team_filter

with f_md:
    with st.container(border=True):
        _filter_label("MATCHDAY", RED)
        if all_mds:
            selected_md = st.selectbox(
                "Matchday", options=all_mds,
                index=all_mds.index(default_md),
                format_func=lambda m: f"Matchday {m}",
                label_visibility="collapsed",
            )
        else:
            selected_md = None
            st.selectbox("Matchday", options=["—"], label_visibility="collapsed", disabled=True)

st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)


def _matches_for(md: int) -> pd.DataFrame:
    df = matches[matches.matchday == md]
    if team_key:
        df = df[(df.home_team_key == team_key) | (df.away_team_key == team_key)]
    return df


# --------------------------------------------------------------- Matchday --
# Un solo selector cubre las 38 (LaLiga) / 34 (Primeira Liga) jornadas de la
# temporada: si ya se jugo se muestra proyectado vs. resultado real, si no,
# la proyeccion del modelo (con el mismo fallback en vivo de siempre).
if selected_md is None:
    st.info("No matches loaded yet for this league/season.")
else:
    day_matches = _matches_for(selected_md)
    is_played = not day_matches.empty and (day_matches.status == "FINISHED").all()

    if is_played:
        st.markdown(f"##### Matchday {selected_md} · {LEAGUE_LABELS[league]} — Played")
        st.caption("Pre-match projection vs. final result")
        for _, m in day_matches.iterrows():
            proj = match_projection(m.home_team_key, m.away_team_key, selected_md,
                                     predictions, snap, mu, gamma, rho)
            confidence = outcome_confidence(proj["p_home"], proj["p_draw"], proj["p_away"], m.result)
            st.markdown(
                C.played_match_row(
                    name_of.get(m.home_team_key, m.home_team_key),
                    name_of.get(m.away_team_key, m.away_team_key),
                    iso2,
                    proj["projected_home"], proj["projected_away"],
                    int(m.home_score), int(m.away_score),
                    selected_md, confidence,
                ),
                unsafe_allow_html=True,
            )
    else:
        st.markdown(f"##### Matchday {selected_md} · {LEAGUE_LABELS[league]} — Upcoming")
        if day_matches.empty:
            st.markdown(
                '<div style="font-size:12px; color:#8892B0;">No matches for this team in this matchday.</div>',
                unsafe_allow_html=True,
            )
        for _, m in day_matches.iterrows():
            proj = match_projection(m.home_team_key, m.away_team_key, selected_md,
                                     predictions, snap, mu, gamma, rho)
            st.markdown(
                C.upcoming_match_card(
                    name_of.get(m.home_team_key, m.home_team_key),
                    name_of.get(m.away_team_key, m.away_team_key),
                    iso2,
                    proj["projected_home"], proj["projected_away"],
                    proj["p_home"], proj["p_draw"], proj["p_away"],
                    proj["top_scorelines"], selected_md, proj["live_projection"],
                ),
                unsafe_allow_html=True,
            )

# --------------------------------------------------------------- Statistics --
st.markdown("##### Model statistics")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div class="fp-card">', unsafe_allow_html=True)
    st.markdown('<span style="font-size:12px; color:#8892B0;">1X2 accuracy by matchday</span>', unsafe_allow_html=True)
    mds, acc = matchday_accuracy_trend(matches, predictions, team_key)
    st.markdown(C.accuracy_trend_svg(mds, acc), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="fp-card">', unsafe_allow_html=True)
    st.markdown('<span style="font-size:12px; color:#8892B0;">Model performance</span>', unsafe_allow_html=True)
    overall_acc = np.mean(acc) if acc else 0.0
    n_sims = int(simulations.n_simulations.iloc[0]) if not simulations.empty else 0
    kpi_values = [overall_acc, overall_acc * 0.4, float(snap["attack"].std()), n_sims / 100]
    kpi_labels = [f"{overall_acc:.0f}%", "exact score ↓", f"attack σ {snap['attack'].std():.2f}", f"{n_sims:,} sims"]
    st.markdown(C.kpi_bars(kpi_values, kpi_labels), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="fp-card">', unsafe_allow_html=True)
    st.markdown('<span style="font-size:12px; color:#8892B0;">Projected table (Top 4)</span>', unsafe_allow_html=True)
    top4 = simulations.sort_values("avg_position").head(4).copy()
    rows = [
        {"pos": i + 1, "name": name_of.get(r.team_key, r.team_key),
         "avg_position": r.avg_position, "prob_champions_league": r.prob_champions_league}
        for i, r in enumerate(top4.itertuples())
    ]
    st.markdown(C.top_table_html(rows), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ Footer --
st.markdown('<div class="fp-footer">Built by Arnoldo Cuéllar</div>', unsafe_allow_html=True)
