"""
theme.py
--------
CSS for the dark/purple theme approved in the mockup (Design artifact,
2026-09-26). A single <style> block injected once at app start; the rest of
the layout is built with Streamlit + custom HTML/CSS via
st.markdown(unsafe_allow_html=True), because the bespoke style (big
score, chips, probability bar, heat map) can't be achieved with Streamlit's
native components.
"""

import streamlit as st

BG_GRADIENT = "linear-gradient(155deg, #08060D 0%, #120B22 55%, #0A0710 100%)"
CARD_BG = "#15111F"
TEXT = "#F4F6FB"
MUTED = "#8892B0"
MUTED_DIM = "#5B5570"
ACCENT = "#8B5CF6"
ACCENT_LIGHT = "#C4B5FF"
ACCENT_DEEP = "#6D28D9"
ACCENT_SOFT = "#A78BFA"
GREEN = "#3DDC97"
GRAY = "#6B6480"
RED = "#FF5C7A"
BORDER_SOFT = "rgba(255,255,255,0.06)"

FLAGS = {
    "ES": {"bg": "#C60B1E", "band": "#FFC400"},
    "PT": {"bg": "#DA020E", "band": "#046A38"},
}


def inject() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&display=swap');

        .stApp {{
            background: {BG_GRADIENT};
            color: {TEXT};
        }}
        [data-testid="stHeader"] {{ background: transparent; }}
        [data-testid="stSidebar"] {{
            background: #0C0814;
            border-right: 1px solid {BORDER_SOFT};
        }}
        .block-container {{ padding-top: 1.5rem; max-width: 1180px; }}
        .mono {{ font-family: "Space Grotesk", system-ui, sans-serif; }}

        .fp-card {{
            background: {CARD_BG};
            border-radius: 20px;
            padding: 20px 22px;
            border: 1px solid {BORDER_SOFT};
        }}
        .fp-card-final {{
            border: 1px solid rgba(139,92,246,0.45);
            box-shadow: 0 0 24px rgba(139,92,246,0.14);
        }}
        .fp-card-proj {{
            border: 1px dashed rgba(196,181,255,0.45);
            background: rgba(139,92,246,0.12);
        }}
        .fp-badge {{
            font-size: 11px; padding: 4px 10px; border-radius: 999px;
            font-weight: 600; letter-spacing: 0.02em;
        }}
        .fp-chip {{
            border-radius: 999px; padding: 8px 14px;
            font-family: "Space Grotesk", system-ui, sans-serif;
            font-weight: 600; font-size: 13px;
        }}
        .fp-eyebrow {{
            font-size: 11px; letter-spacing: 0.08em; color: {MUTED};
            text-transform: uppercase;
        }}
        .fp-score {{
            font-family: "Space Grotesk", system-ui, sans-serif;
            font-weight: 700;
        }}
        hr.fp-divider {{
            border: none; height: 2px; margin: 4px 0 18px 0;
            background: linear-gradient(90deg, rgba(139,92,246,0) 0%, {ACCENT} 50%, rgba(139,92,246,0) 100%);
        }}

        /* -- Slicers (league/team/matchday selectbox) --
           Streamlit 1.4x+ builds st.selectbox on top of react-aria, with
           stable data-testid/role attributes (unlike the
           st-emotion-cache-* classes that change from build to build) --
           that is why all the selectors below rely on those attributes,
           never on a generated class name. */

        /* container card for each filter (st.container(border=True)) */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: {CARD_BG} !important;
            border: 1px solid {BORDER_SOFT} !important;
            border-radius: 16px !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] {{
            gap: 0.35rem;
        }}

        div[data-testid="stSelectbox"] [role="group"] {{
            background: {CARD_BG} !important;
            border: 1px solid {BORDER_SOFT} !important;
            border-radius: 12px !important;
            transition: border-color 0.15s ease;
        }}
        div[data-testid="stSelectbox"] [role="group"]:focus-within {{
            border-color: rgba(139,92,246,0.55) !important;
        }}
        div[data-testid="stSelectbox"] input[role="combobox"] {{
            color: {TEXT} !important;
            font-size: 13px !important;
            font-weight: 600 !important;
        }}
        div[data-testid="stSelectbox"] button[aria-haspopup="listbox"] {{
            color: {MUTED_DIM} !important;
        }}
        /* dropdown menu (it is mounted in a portal, which is why it sits
           loose and not nested under stSelectbox) */
        [role="listbox"] {{
            background: {CARD_BG} !important;
            border: 1px solid rgba(139,92,246,0.35) !important;
            border-radius: 12px !important;
            overflow: hidden;
        }}
        [role="listbox"] [role="option"] {{
            color: {TEXT} !important;
            font-size: 13px !important;
        }}
        [role="listbox"] [role="option"][aria-selected="true"],
        [role="listbox"] [role="option"]:hover {{
            background: rgba(139,92,246,0.18) !important;
        }}

        /* Prev/Next buttons of the matchday selector -- same dark/purple
           treatment as the selectbox, instead of Streamlit's default light
           button. It anchors to the "st-key-<key>" class that Streamlit
           generates for every widget with `key=...` (a documented, stable
           mechanism), instead of data-testid="stVerticalBlockBorderWrapper"
           -- that wrapper no longer wraps the buttons in the current
           version of Streamlit Cloud (verified via live DOM), which is why
           the previous rule never matched. */
        div[class*="st-key-md_select_"] button {{
            background: {CARD_BG} !important;
            border: 1px solid {BORDER_SOFT} !important;
            color: {TEXT} !important;
            border-radius: 10px !important;
            min-height: 2.35rem;
            padding: 0 !important;
        }}
        div[class*="st-key-md_select_"] button * {{
            color: {TEXT} !important;
        }}
        div[class*="st-key-md_select_"] button:hover:not(:disabled) {{
            border-color: rgba(139,92,246,0.55) !important;
        }}
        div[class*="st-key-md_select_"] button:hover:not(:disabled) * {{
            color: {ACCENT_LIGHT} !important;
        }}
        div[class*="st-key-md_select_"] button:disabled {{
            opacity: 0.3;
        }}

        /* -- Layout classes used by components.py. They replace the old inline
           styles so the @media rules at the bottom can reflow them on phones. -- */
        .fp-pair {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .fp-pair > .fp-card {{ flex: 1; min-width: 0; }}
        .fp-card-head {{
            display: flex; justify-content: space-between; align-items: center;
            gap: 8px; flex-wrap: wrap; margin-bottom: 14px;
        }}
        .fp-badges {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
        .fp-teams {{
            display: flex; align-items: center; justify-content: space-between; gap: 10px;
        }}
        .fp-team {{ flex: 1; min-width: 0; font-size: 15px; font-weight: 600; overflow-wrap: break-word; }}
        .fp-team-away {{ text-align: right; }}
        .fp-scorebox {{ display: flex; flex-direction: column; align-items: center; gap: 8px; }}
        .fp-chips {{ display: flex; gap: 12px; flex-wrap: wrap; }}
        .fp-toprow {{
            display: flex; justify-content: space-between; gap: 12px;
            padding: 6px 8px; border-radius: 8px;
        }}
        .fp-toprow-name {{ min-width: 0; overflow-wrap: break-word; }}
        .fp-toprow-val {{ white-space: nowrap; }}

        .fp-footer {{
            text-align: center; font-size: 12px; color: {MUTED_DIM};
            margin-top: 32px; padding-top: 18px;
            border-top: 1px solid {BORDER_SOFT};
        }}

        /* ------------------------------------------------------------------
           Phones and small tablets. The inline-style layout above is the
           desktop layout; everything below only kicks in on narrow screens.
           ------------------------------------------------------------------ */

        /* The 4 filter cards = the only st.columns() row with exactly 4
           columns. Structural selector on purpose (no key/class needed):
           2x2 grid up to 900px; on phones Season+League share one row and
           Team / Matchday get a full row each. Without this, Streamlit
           stacks the 4 cards one under another (~1.5 screens of filters). */
        @media (max-width: 900px) {{
            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(4)):not(:has(> div:nth-child(5))) {{
                display: grid !important;
                grid-template-columns: 1fr 1fr;
                gap: 0.6rem !important;
            }}
            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(4)):not(:has(> div:nth-child(5))) > div {{
                width: auto !important; min-width: 0 !important; flex: none !important;
            }}
        }}

        @media (max-width: 640px) {{
            /* the league name is the longest label: give it more width than the season */
            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(4)):not(:has(> div:nth-child(5))) {{
                grid-template-columns: 6fr 7fr;
            }}
            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(4)):not(:has(> div:nth-child(5))) > div:nth-child(n+3) {{
                grid-column: 1 / -1;
            }}

            /* Prev / select / Next stay on ONE row (Streamlit would stack the
               3 columns). The row is the only one with exactly 3 columns. */
            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) {{
                flex-wrap: nowrap !important; flex-direction: row !important;
                gap: 0.4rem !important; align-items: center;
            }}
            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div {{
                min-width: 0 !important; width: auto !important;
            }}
            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(1),
            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(3) {{
                flex: 0 0 2.75rem !important;
            }}
            div[data-testid="stHorizontalBlock"]:has(> div:nth-child(3)):not(:has(> div:nth-child(4))) > div:nth-child(2) {{
                flex: 1 1 0 !important;
            }}

            /* header: solid bar so the Fork/GitHub/menu icons don't float
               over the content while scrolling; the content starts below it */
            [data-testid="stHeader"] {{
                background: rgba(8,6,13,0.94) !important;
                backdrop-filter: blur(6px);
            }}
            .block-container {{
                padding: 3.6rem 0.9rem 5rem 0.9rem !important;
            }}

            /* compact filter cards */
            div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 14px !important; }}
            div[data-testid="stVerticalBlockBorderWrapper"] > div {{ padding: 0.55rem 0.5rem !important; }}

            /* touch targets: 44px, and 16px text in the inputs (iOS Safari
               zooms the whole page when a focused input is smaller) */
            div[data-testid="stSelectbox"] input[role="combobox"] {{ font-size: 16px !important; padding-left: 0.1rem !important; }}
            div[data-testid="stSelectbox"] [role="group"] {{ min-height: 2.75rem; }}
            [role="listbox"] [role="option"] {{ font-size: 15px !important; padding-top: 0.6rem; padding-bottom: 0.6rem; }}
            div[class*="st-key-md_select_"] button {{ min-height: 2.75rem; font-size: 20px; }}

            h5 {{ font-size: 1.05rem !important; line-height: 1.35; }}

            /* match cards */
            .fp-card {{ padding: 14px 14px; border-radius: 16px; }}
            .fp-pair {{ flex-direction: column; gap: 12px; margin-bottom: 12px; }}
            .fp-card-head {{ margin-bottom: 10px; }}

            /* score (flag + result) on its own centered row; both team
               names share the row below, so a long name like "RCD Espanyol
               de Barcelona" gets ~140px instead of ~100px */
            .fp-teams {{ flex-wrap: wrap; row-gap: 10px; }}
            .fp-scorebox {{ order: -1; flex: 1 0 100%; flex-direction: row; justify-content: center; gap: 14px; }}
            .fp-team {{ flex: 1 1 40%; font-size: 14px; }}
            .fp-chips {{ gap: 8px; }}
            .fp-chip {{ padding: 7px 12px; font-size: 12.5px; }}

            .fp-toprow {{ flex-wrap: wrap; row-gap: 2px; font-size: 13px; }}
            .fp-toprow-name {{ flex: 1 1 100%; }}
            .fp-toprow-val {{ font-size: 12px; color: {MUTED}; }}

            .fp-footer {{ margin-top: 20px; }}
        }}

        /* very narrow phones (360px): slightly smaller select text so
           "LaLiga EA Sports" still fits next to the season */
        @media (max-width: 380px) {{
            div[data-testid="stSelectbox"] input[role="combobox"] {{ font-size: 14px !important; }}
            div[data-testid="stVerticalBlockBorderWrapper"] > div {{ padding: 0.55rem 0.4rem !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
