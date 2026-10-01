"""
components.py
--------------
Builds the HTML/SVG blocks of the approved theme (scoreboard, probability
bar, scoreline chips, KPIs, heat map, projected table). Each function
returns an HTML string meant for st.markdown(html, unsafe_allow_html=True)
-- they are not native Streamlit components because the bespoke look of the
mockup can't be achieved with the default widgets.

All the visible text in the app (what these functions return) is in
English -- code comments/docstrings are in English too.
"""

from __future__ import annotations

from src.app.theme import (
    ACCENT_LIGHT, MUTED, MUTED_DIM,
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
    # .strip(): this function is interpolated INSIDE other multiline
    # f-strings (played_match_row, upcoming_match_card). Without strip(), the
    # leading newline of this block, plus the indentation of the line that
    # calls it, leaves a line made up only of spaces right before the away
    # team's div -- Streamlit's Markdown parser reads that as the end of the
    # HTML block and the next <div> (indented 4 spaces) as a code block,
    # showing the away team's name as raw text instead of rendered.
    return f"""
    <div style="display:flex; flex-direction:column; align-items:center; gap:8px;">
      {flag_svg(iso2)}
      <div class="fp-score" style="font-size:{size}px; color:{color};">{home_txt} – {away_txt}</div>
    </div>
    """.strip()


def _accuracy_badge(accuracy_pct: float) -> str:
    """Badge showing how close the projected exact scoreline was to the
    final result (see data_access.scoreline_accuracy). An exact scoreline
    (100%) is shown as a check mark instead of a number. 3-level color so
    it reads at a glance: green = very close, purple = reasonable,
    red = far."""
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


def _quality_color(quality: float) -> str:
    """Interpolates in RGB between RED (quality=0, worst) and GREEN
    (quality=1, best) -- the same color tokens the rest of the app uses
    (the scoreline_accuracy badge, the Home/Draw/Away bar), so the KPI tiles
    speak the same visual language. 'quality' arrives already normalized
    0-1 from data_access.py/app.py (each metric defines its own sense of
    "better" before getting here -- e.g. RPS and goal error are better the
    lower they are, which is why their quality = 1 - normalized value, not
    the raw value)."""
    q = max(0.0, min(1.0, quality))
    red, green = (0xFF, 0x5C, 0x7A), (0x3D, 0xDC, 0x97)
    r, g, b = (round(red[i] + (green[i] - red[i]) * q) for i in range(3))
    return f"#{r:02X}{g:02X}{b:02X}"


def kpi_tiles(tiles: list[dict]) -> str:
    """tiles: [{'value': str, 'label': str, 'quality': float | None}, ...].

    Replaces the old kpi_bars(): there, 4 metrics with different units and
    scale (accuracy %, Brier score, rating deviation, simulation count)
    were forced into a bar with relative height, suggesting a magnitude
    comparison between them that didn't exist -- a dataviz anti-pattern
    (mixing units on a single axis). Here each metric is its own tile with
    its big number, with no shared axis or bar.

    'quality' (0 to 1, already normalized by the caller) colors the number
    in a red->green gradient depending on how good THAT value is for that
    specific metric. 'quality'=None leaves the number in the normal text
    color, for metrics that are not a quality indicator (e.g. the number
    of Monte Carlo simulations: more simulations is not a "better model",
    it just says how much compute was used)."""
    cells = ""
    for t in tiles:
        color = _quality_color(t["quality"]) if t.get("quality") is not None else TEXT
        cells += (
            f'<div style="min-width:0; text-align:center;">'
            f'<div class="mono" style="font-size:22px; font-weight:700; color:{color};">{t["value"]}</div>'
            f'<div style="font-size:11px; color:{MUTED}; margin-top:2px;">{t["label"]}</div>'
            f'</div>'
        )
    return (
        f'<div style="display:grid; grid-template-columns: repeat(2, 1fr); '
        f'gap:18px 14px; margin-top:10px;">{cells}</div>'
    )


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
