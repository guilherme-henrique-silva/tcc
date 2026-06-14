"""Helper de tema claro/escuro reutilizável."""

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class _Palette:
    """Esquema de cores com 5 papéis semânticos."""

    primary: str
    secondary: str
    tertiary: str
    text: str
    highlight: str
    background: str
    surface: str


_LIGHT = _Palette(
    primary="#FF6B35",
    secondary="#F7F7F7",
    tertiary="#E8EAF0",
    text="#1A1A2E",
    highlight="#FF8A5B",
    background="#FFFFFF",
    surface="#F0F2F6",
)

_DARK = _Palette(
    primary="#FF8A5B",
    secondary="#1A1C24",
    tertiary="#262730",
    text="#FAFAFA",
    highlight="#FFB38A",
    background="#0E1117",
    surface="#1A1C24",
)

_LIGHT_CSS = f"""
<style>
    .stApp {{ background-color: {_LIGHT.background}; color: {_LIGHT.text}; }}
    section[data-testid="stSidebar"] {{ background-color: {_LIGHT.surface}; }}
    section[data-testid="stSidebar"] * {{ color: {_LIGHT.text}; }}
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp label,
    .stApp li, .stApp span, .stApp div[data-testid="stMarkdownContainer"] {{
        color: {_LIGHT.text};
    }}
    .stApp [data-testid="stMetricValue"] {{ color: {_LIGHT.text}; }}
    .stApp code {{ color: {_LIGHT.primary}; }}
    div[data-testid="stExpander"] {{ background-color: {_LIGHT.tertiary}; color: {_LIGHT.text}; }}
    div[data-testid="stNotification"] {{ color: {_LIGHT.text}; }}
    .stApp a {{ color: {_LIGHT.primary}; }}
</style>
"""

_DARK_CSS = f"""
<style>
    .stApp {{ background-color: {_DARK.background}; color: {_DARK.text}; }}
    section[data-testid="stSidebar"] {{ background-color: {_DARK.surface}; }}
    section[data-testid="stSidebar"] * {{ color: {_DARK.text}; }}
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp label,
    .stApp li, .stApp span, .stApp div[data-testid="stMarkdownContainer"] {{
        color: {_DARK.text};
    }}
    .stApp [data-testid="stMetricValue"] {{ color: {_DARK.text}; }}
    .stApp code {{ color: {_DARK.highlight}; }}
    div[data-testid="stExpander"], div[data-testid="stNotification"] {{
        background-color: {_DARK.surface}; color: {_DARK.text};
    }}
</style>
"""


def apply_theme() -> None:
    """Renderiza o toggle de dark mode no sidebar e aplica a paleta correspondente.

    A preferência fica em st.session_state["dark_mode"], persistindo entre páginas.
    """
    st.session_state.setdefault("dark_mode", False)
    st.sidebar.toggle("🌙 Modo escuro", key="dark_mode")

    if st.session_state["dark_mode"]:
        st.markdown(_DARK_CSS, unsafe_allow_html=True)
    else:
        st.markdown(_LIGHT_CSS, unsafe_allow_html=True)
