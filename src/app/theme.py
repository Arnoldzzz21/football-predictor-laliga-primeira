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
            border: 1px dashed rgba(196,181,255,0.45);
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

        /* -- Segmentadores (selectbox de liga/equipo/jornada) --
           Streamlit 1.4x+ arma st.selectbox sobre react-aria, con
           data-testid/role estables (a diferencia de las clases
           st-emotion-cache-* que cambian de build a build) -- por eso
           todos los selectores de abajo se apoyan en esos atributos,
           nunca en un nombre de clase generado. */

        /* tarjeta contenedora de cada filtro (st.container(border=True)) */
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
        /* menu desplegable (se monta en un portal, por eso va suelto y no
           anidado bajo stSelectbox) */
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

        /* botones Prev/Next del selector de jornada -- mismo tratamiento
           oscuro/morado que el selectbox, en vez del boton claro por
           defecto de Streamlit. Se ancla a la clase "st-key-<key>" que
           Streamlit genera para todo widget con `key=...` (mecanismo
           documentado y estable), en vez de data-testid="stVerticalBlockBorderWrapper"
           -- ese wrapper ya no envuelve a los botones en la version actual
           de Streamlit Cloud (verificado via DOM live), por eso la regla
           anterior nunca hacia match. */
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
