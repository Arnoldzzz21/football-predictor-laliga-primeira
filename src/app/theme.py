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

        .fp-footer {{
            text-align: center; font-size: 12px; color: {MUTED_DIM};
            margin-top: 32px; padding-top: 18px;
            border-top: 1px solid {BORDER_SOFT};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
