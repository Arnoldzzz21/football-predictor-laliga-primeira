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

import pandas as pd
import streamlit as st

from src.app import theme, components as C
from src.app.theme import ACCENT, ACCENT_LIGHT, GREEN, RED
from src.app.data_access import (
    LEAGUE_LABELS, LEAGUE_FLAG, AVAILABLE_SEASONS,
    load_teams_master, load_matches, load_team_ratings,
    load_match_predictions, load_season_simulations,
    team_name_map, active_season_teams,
    latest_ratings_snapshot, global_params, match_projection,
    matchday_status, matchday_accuracy_trend, scoreline_accuracy,
    matchday_rps_score, avg_real_goals, avg_prob_on_actual,
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
# Las 4 tarjetas se llenan en orden de dependencia (season/liga -> datos de
# esa season+liga -> equipo/jornada), pero cada `with` coloca su contenido
# en la columna que le corresponde sin importar el orden de ejecucion.
f_season, f_league, f_team, f_md = st.columns(4)

with f_season:
    with st.container(border=True):
        _filter_label("SEASON", ACCENT)
        # Por ahora AVAILABLE_SEASONS solo trae la temporada activa (ver
        # nota en data_access.py) -- el slicer ya queda listo para cuando
        # arranque la proxima temporada, sin mas cambios en la UI.
        season = st.selectbox(
            "Season", options=AVAILABLE_SEASONS, label_visibility="collapsed",
        )

with f_league:
    with st.container(border=True):
        _filter_label("LEAGUE", ACCENT_LIGHT)
        league = st.selectbox(
            "League", options=list(LEAGUE_LABELS.keys()),
            format_func=lambda k: LEAGUE_LABELS[k], label_visibility="collapsed",
        )

matches = load_matches(league, season)
ratings = load_team_ratings(league, season)
predictions = load_match_predictions(league, season)
simulations = load_season_simulations(league, season)
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

# Navegacion de jornada: botones Prev/Next ademas del selectbox, para no
# depender de hacer scroll (o escribir a buscar) dentro de una lista de 38
# opciones -- el usuario reporto que el selectbox solo no era intuitivo
# para moverse por jornadas lejos de la actual.
md_key = f"md_select_{season}_{league}"
if md_key not in st.session_state or st.session_state[md_key] not in all_mds:
    st.session_state[md_key] = default_md

with f_md:
    with st.container(border=True):
        _filter_label("MATCHDAY", RED)
        if all_mds:
            current_idx = all_mds.index(st.session_state[md_key])
            nav_prev, nav_mid, nav_next = st.columns([1, 5, 1], gap="small")
            with nav_prev:
                if st.button("‹", key=f"{md_key}_prev", use_container_width=True,
                             disabled=(current_idx == 0), help="Previous matchday"):
                    st.session_state[md_key] = all_mds[current_idx - 1]
            with nav_next:
                if st.button("›", key=f"{md_key}_next", use_container_width=True,
                             disabled=(current_idx == len(all_mds) - 1), help="Next matchday"):
                    st.session_state[md_key] = all_mds[current_idx + 1]
            with nav_mid:
                selected_md = st.selectbox(
                    "Matchday", options=all_mds,
                    format_func=lambda m: f"Matchday {m}",
                    label_visibility="collapsed",
                    key=md_key,
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
    finished_count = int((day_matches.status == "FINISHED").sum())
    has_played = finished_count > 0
    all_played = not day_matches.empty and finished_count == len(day_matches)

    # Estado por jornada basado en si al menos un partido ya se jugo (no si
    # TODOS se jugaron): una jornada con un partido aplazado/reprogramado
    # (status POSTPONED/TIMED) sigue contando como jugada para los que ya
    # tienen resultado -- cada partido se renderiza segun su propio status,
    # no segun el status agregado de la jornada.
    if has_played:
        header_label = "Played" if all_played else f"In progress · {finished_count}/{len(day_matches)} played"
        st.markdown(f"##### Matchday {selected_md} · {LEAGUE_LABELS[league]} — {header_label}")
        st.caption("Pre-match projection vs. final result" if all_played
                   else "Pre-match projection vs. final result — some matches are still pending (postponed/rescheduled)")
    else:
        st.markdown(f"##### Matchday {selected_md} · {LEAGUE_LABELS[league]} — Upcoming")
        if day_matches.empty:
            st.markdown(
                '<div style="font-size:12px; color:#8892B0;">No matches for this team in this matchday.</div>',
                unsafe_allow_html=True,
            )

    for _, m in day_matches.iterrows():
        # Blowout scoreline for clear favorites ONLY in upcoming matches;
        # already-played (FINISHED) matches keep the original projected scoreline.
        proj = match_projection(m.home_team_key, m.away_team_key, selected_md,
                                 predictions, snap, mu, gamma, rho,
                                 show_blowout=(m.status != "FINISHED"))
        if m.status == "FINISHED":
            accuracy_pct = scoreline_accuracy(
                proj["projected_home"], proj["projected_away"],
                int(m.home_score), int(m.away_score),
            )
            st.markdown(
                C.played_match_row(
                    name_of.get(m.home_team_key, m.home_team_key),
                    name_of.get(m.away_team_key, m.away_team_key),
                    iso2,
                    proj["projected_home"], proj["projected_away"],
                    int(m.home_score), int(m.away_score),
                    selected_md, accuracy_pct,
                ),
                unsafe_allow_html=True,
            )
        else:
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
# Antes esta seccion tenia 3 columnas: un line chart de tendencia (1X2
# accuracy by matchday), un bar chart de "Model performance" que mezclaba
# 4 metricas de distinta unidad en un solo eje (anti-patron de dataviz), y
# la tabla proyectada. Se reemplazan las primeras 2 por una sola tarjeta de
# 4 KPIs individuales (cada uno con su propio color rojo->verde segun que
# tan bueno es el valor), mas legible para alguien que ve la app por
# primera vez.
st.markdown("##### Model statistics")
col_kpi, col_top4 = st.columns([2, 1])

with col_kpi:
    # Los 4 KPIs se calculan solo sobre los partidos de la JORNADA
    # seleccionada en el filtro MATCHDAY (no sobre toda la temporada) --
    # asi la seccion reacciona al filtro igual que las tarjetas de
    # partidos de arriba. Si la jornada elegida todavia no se jugo
    # (ningun partido FINISHED), las funciones de mas abajo ya devuelven
    # None/listas vacias con este subset y las tarjetas muestran "n/a".
    stats_matches = matches[matches.matchday == selected_md] if selected_md is not None else matches.iloc[0:0]

    mds, acc = matchday_accuracy_trend(stats_matches, predictions, team_key)
    md_acc = acc[0] if acc else None

    rps = matchday_rps_score(stats_matches, predictions, team_key)
    real_goals, is_season_avg = avg_real_goals(stats_matches, matches, team_key)
    prob_actual = avg_prob_on_actual(stats_matches, predictions, team_key)

    tiles = [
        {
            "value": f"{md_acc:.0f}%" if md_acc is not None else "n/a",
            "label": f"1X2 accuracy · MD{selected_md}" if selected_md is not None else "1X2 accuracy",
            "quality": (md_acc / 100) if md_acc is not None else None,
        },
        {
            "value": f"{rps:.3f}" if rps is not None else "n/a",
            "label": "RPS (lower is better)",
            # RPS ya esta acotado 0-1 (mientras mas bajo, mejor calibrado).
            "quality": (1 - rps) if rps is not None else None,
        },
        {
            "value": f"{real_goals:.1f}" if real_goals is not None else "n/a",
            # Si la jornada seleccionada ya se jugo, es su propio promedio;
            # si no, cae al promedio de la temporada (ver avg_real_goals).
            "label": (f"Avg goals · MD{selected_md}" if real_goals is not None and not is_season_avg
                      else "Avg goals · season so far"),
            # No es una metrica de calidad del modelo, solo describe cuanto
            # se anoto -- quality=None deja el numero sin colorear (ver
            # kpi_tiles()).
            "quality": None,
        },
        {
            "value": f"{prob_actual:.0f}%" if prob_actual is not None else "n/a",
            "label": "Avg prob on actual result",
            # Ya viene 0-100%, mientras mas alto mejor -- se usa directo.
            "quality": (prob_actual / 100) if prob_actual is not None else None,
        },
    ]
    st.markdown(
        '<div class="fp-card">'
        '<span style="font-size:12px; color:#8892B0;">Model performance</span>'
        + C.kpi_tiles(tiles) +
        '</div>',
        unsafe_allow_html=True,
    )

with col_top4:
    top4 = simulations.sort_values("avg_position").head(4).copy()
    rows = [
        {"pos": i + 1, "name": name_of.get(r.team_key, r.team_key),
         "avg_position": r.avg_position, "prob_champions_league": r.prob_champions_league}
        for i, r in enumerate(top4.itertuples())
    ]
    st.markdown(
        '<div class="fp-card">'
        '<span style="font-size:12px; color:#8892B0;">Projected table (Top 4)</span>'
        + C.top_table_html(rows) +
        '</div>',
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------ Footer --
st.markdown('<div class="fp-footer">Built by Arnoldo Cuéllar</div>', unsafe_allow_html=True)
