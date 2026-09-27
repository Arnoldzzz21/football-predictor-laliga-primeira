"""
components.py
--------------
Genera los bloques HTML/SVG del tema aprobado (scoreboard, barra de
probabilidad, chips de resultados, KPIs, mapa de calor, tabla proyectada).
Cada funcion regresa un string HTML pensado para st.markdown(html,
unsafe_allow_html=True) -- no son componentes nativos de Streamlit porque
el look bespoke del mockup no se logra con los widgets por defecto.

Todo el texto visible en la app (lo que regresan estas funciones) va en
ingles -- los comentarios/docstrings del codigo se quedan en espanol.
"""

from __future__ import annotations

from src.app.theme import (
    ACCENT, ACCENT_LIGHT, ACCENT_DEEP, ACCENT_SOFT, MUTED, MUTED_DIM,
    GREEN, GRAY, RED, TEXT, FLAGS,
)


def flag_svg(iso2: str, w: int = 28, h: int = 19) -> str:
    f = FLAGS.get(iso2)
    if not f:
        return f'<svg width="{w}" height="{h}" viewBox="0 0 30 20"><rect width="30" height="20" fill="#3A3550"/></svg>'
    if iso2 == "ES":
        return (f'<svg width="{w}" height="{h}" viewBox="0 0 30 20">'
                f'<rect width="30" height="20" fill="{f["bg"]}"/>'
                f'<rect y="5" width="30" height="10" fill="{f["band"]}"/></svg>')
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 30 20">'
            f'<rect width="30" height="20" fill="{f["bg"]}"/>'
            f'<rect width="12" height="20" fill="{f["band"]}"/></svg>')


def _score_block(iso2: str, home_txt: str, away_txt: str, color: str, size: int = 30) -> str:
    # .strip(): esta funcion se interpola DENTRO de otros f-strings
    # multilinea (played_match_row, upcoming_match_card). Sin strip(), el
    # salto de linea inicial de este bloque, sumado a la indentacion de la
    # linea que lo llama, deja una linea compuesta solo por espacios justo
    # antes del div del equipo visitante -- el parser de Markdown de
    # Streamlit interpreta eso como fin del bloque HTML y el siguiente
    # <div> (indentado 4 espacios) como bloque de codigo, mostrando el
    # nombre del equipo visitante como texto crudo en vez de renderizado.
    return f"""
    <div style="display:flex; flex-direction:column; align-items:center; gap:8px;">
      {flag_svg(iso2)}
      <div class="fp-score" style="font-size:{size}px; color:{color};">{home_txt} – {away_txt}</div>
    </div>
    """.strip()


def _accuracy_badge(accuracy_pct: float) -> str:
    """Badge de que tan cerca estuvo el marcador exacto proyectado del
    resultado final (ver data_access.scoreline_accuracy). Marcador exacto
    (100%) se muestra como un check en vez de un numero. Color en 3 niveles
    para que se lea de un vistazo: verde = muy cerca, morado = razonable,
    rojo = lejos."""
    if accuracy_pct >= 100:
        return (f'<span class="fp-badge" style="background:rgba(61,220,151,0.16); color:{GREEN};" '
                f'title="The projected scoreline matched the final result exactly">'
                f'✓ Exact</span>')
    if accuracy_pct >= 80:
        bg, color = "rgba(61,220,151,0.16)", GREEN
    elif accuracy_pct >= 40:
        bg, color = "rgba(139,92,246,0.18)", ACCENT_LIGHT
    else:
        bg, color = "rgba(255,92,122,0.14)", RED
    return (f'<span class="fp-badge" style="background:{bg}; color:{color};" '
            f'title="How close the projected scoreline was to the final result">'
            f'🎯 {accuracy_pct:.0f}%</span>')


def played_match_row(home_name: str, away_name: str, iso2: str,
                      proj_h: int, proj_a: int, final_h: int, final_a: int,
                      matchday: int, accuracy_pct: float) -> str:
    return f"""
    <div style="display:flex; gap:20px; margin-bottom:20px;">
      <div class="fp-card fp-card-proj" style="flex:1;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
          <span class="fp-eyebrow">Projected</span>
          <span class="fp-badge" style="background:rgba(148,142,168,0.14); color:{MUTED_DIM};">Pre-match</span>
        </div>
        <div style="display:flex; align-items:center; justify-content:space-between; gap:10px;">
          <div style="flex:1;"><div style="font-size:15px; font-weight:600;">{home_name}</div></div>
          {_score_block(iso2, proj_h, proj_a, MUTED_DIM)}
          <div style="flex:1; text-align:right;"><div style="font-size:15px; font-weight:600;">{away_name}</div></div>
        </div>
      </div>
      <div class="fp-card fp-card-final" style="flex:1;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
          <span class="fp-eyebrow">Final result</span>
          <div style="display:flex; gap:8px; align-items:center;">
            {_accuracy_badge(accuracy_pct)}
            <span class="fp-badge" style="background:rgba(139,92,246,0.18); color:{ACCENT_LIGHT};">Final · MD{matchday}</span>
          </div>
        </div>
        <div style="display:flex; align-items:center; justify-content:space-between; gap:10px;">
          <div style="flex:1;"><div style="font-size:15px; font-weight:600;">{home_name}</div></div>
          {_score_block(iso2, final_h, final_a, TEXT)}
          <div style="flex:1; text-align:right;"><div style="font-size:15px; font-weight:600;">{away_name}</div></div>
        </div>
      </div>
    </div>
    """


def upcoming_match_card(home_name: str, away_name: str, iso2: str,
                         proj_h: int, proj_a: int,
                         p_home: float, p_draw: float, p_away: float,
                         top_scorelines: list[dict], matchday: int,
                         live_projection: bool) -> str:
    chips = ""
    for i, sc in enumerate(top_scorelines):
        highlighted = i == 0
        bg = "rgba(139,92,246,0.14)" if highlighted else "#1E1830"
        border = f"1px solid {'rgba(139,92,246,0.5)' if highlighted else 'rgba(255,255,255,0.06)'}"
        color = ACCENT_LIGHT if highlighted else "#C7CEE3"
        chips += (f'<div class="fp-chip" style="background:{bg}; border:{border}; color:{color};">'
                  f'{sc["home"]}–{sc["away"]} · {sc["prob"] * 100:.0f}%</div>')

    live_note = (
        f'<div style="font-size:11px; color:{MUTED_DIM}; margin-top:4px;">'
        f'Live projection using the latest team ratings '
        f'(the predictions pipeline hasn’t run for this matchday yet)</div>'
    ) if live_projection else ""

    return f"""
    <div class="fp-card" style="border:1px solid rgba(139,92,246,0.3); margin-bottom:20px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;">
        <span class="fp-eyebrow">Model projection</span>
        <span class="fp-badge" style="background:rgba(139,92,246,0.18); color:{ACCENT_LIGHT};">Upcoming · MD{matchday}</span>
      </div>
      <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:18px;">
        <div style="flex:1;"><div style="font-size:16px; font-weight:600;">{home_name}</div></div>
        {_score_block(iso2, proj_h, proj_a, ACCENT_LIGHT, size=28)}
        <div style="flex:1; text-align:right;"><div style="font-size:16px; font-weight:600;">{away_name}</div></div>
      </div>
      {live_note}
      <div style="margin-top:16px;">
        <div style="display:flex; height:10px; border-radius:999px; overflow:hidden; background:#1E1830;">
          <div style="width:{p_home*100:.1f}%; background:{GREEN};"></div>
          <div style="width:{p_draw*100:.1f}%; background:{GRAY};"></div>
          <div style="width:{p_away*100:.1f}%; background:{RED};"></div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:12px; color:{MUTED}; margin-top:8px;">
          <span>Home {p_home*100:.0f}%</span><span>Draw {p_draw*100:.0f}%</span><span>Away {p_away*100:.0f}%</span>
        </div>
      </div>
      <div style="margin-top:18px; display:flex; flex-direction:column; gap:10px;">
        <span class="fp-eyebrow">Most likely scorelines</span>
        <div style="display:flex; gap:12px; flex-wrap:wrap;">{chips}</div>
      </div>
    </div>
    """


def accuracy_trend_svg(matchdays: list[int], values_pct: list[float]) -> str:
    if not matchdays:
        return f'<div style="font-size:12px; color:{MUTED};">No played matchdays with a projection to compare yet.</div>'
    w, h, pad = 300, 90, 8
    n = len(matchdays)
    xs = [pad + i * (w - 2 * pad) / max(n - 1, 1) for i in range(n)]
    ys = [h - pad - (v / 100) * (h - 2 * pad) for v in values_pct]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = poly + f" {xs[-1]:.1f},{h} {xs[0]:.1f},{h}"
    last_x, last_y = xs[-1], ys[-1]
    return f"""
    <svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none">
      <defs>
        <linearGradient id="fpArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="{ACCENT}" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="{ACCENT}" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <polygon points="{area}" fill="url(#fpArea)"/>
      <polyline points="{poly}" fill="none" stroke="{ACCENT}" stroke-width="3"/>
      <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4" fill="{ACCENT_LIGHT}"/>
    </svg>
    <div style="display:flex; justify-content:space-between; font-size:11px; color:{MUTED_DIM};">
      <span>MD{matchdays[0]}</span><span>MD{matchdays[-1]}</span>
    </div>
    """


def kpi_bars(values: list[float], labels: list[str]) -> str:
    max_v = max(values) or 1
    colors = [ACCENT_DEEP, ACCENT, ACCENT_SOFT, ACCENT_LIGHT]
    bars = ""
    for i, v in enumerate(values):
        pct = max(6, v / max_v * 100)
        bars += f'<div style="width:22px; height:{pct:.0f}%; background:{colors[i % 4]}; border-radius:4px 4px 0 0;"></div>'
    label_row = "".join(f'<span>{l}</span>' for l in labels)
    return f"""
    <div style="display:flex; align-items:flex-end; gap:14px; height:70px;">{bars}</div>
    <div style="display:flex; justify-content:space-between; font-size:11px; color:#C7CEE3; margin-top:6px;">{label_row}</div>
    """


def top_table_html(rows: list[dict]) -> str:
    """rows: [{'pos', 'name', 'avg_position', 'prob_champions_league'}, ...]"""
    body = ""
    for r in rows:
        hi = r["pos"] <= 4
        bg = "background:rgba(139,92,246,0.12);" if hi else ""
        body += (
            f'<div style="display:flex; justify-content:space-between; padding:6px 8px; border-radius:8px; {bg}">'
            f'<span>{r["pos"]}. {r["name"]}</span>'
            f'<span class="mono">{r["avg_position"]:.1f} · {r["prob_champions_league"]*100:.0f}% UCL</span></div>'
        )
    return f'<div style="display:flex; flex-direction:column; gap:8px; font-size:13px;">{body}</div>'
