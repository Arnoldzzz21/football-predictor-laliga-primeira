"""
theme.py
--------
CSS del tema oscuro/morado aprobado en el mockup (Design artifact,
2026-09-26). Un solo bloque <style> inyectado una vez al inicio de la app;
todo el resto del layout se arma con Streamlit + HTML/CSS propio via
st.markdown(unsafe_allow_html=True), porque el estilo bespoke (score
grande, chips, barra de probabilidad, mapa de calor) no se logra con los
componentes nativos de Streamlit.
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
            border: 1px dashed rgba(148,142,168,0.35);
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
        </style>
        """,
        unsafe_allow_html=True,
    )
