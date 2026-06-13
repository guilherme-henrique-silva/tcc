"""Helper de tema claro/escuro reutilizável (Requisito 2 do spec)."""

import streamlit as st

# Paleta escura complementar ao tema claro de .streamlit/config.toml
# (primaryColor #FF6B35). Injetada via CSS para alternância dinâmica sem reload.
_DARK_CSS = """
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    section[data-testid="stSidebar"] { background-color: #1A1C24; }
    section[data-testid="stSidebar"] * { color: #FAFAFA; }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp label,
    .stApp li, .stApp span, .stApp div[data-testid="stMarkdownContainer"] {
        color: #FAFAFA;
    }
    .stApp [data-testid="stMetricValue"] { color: #FAFAFA; }
    .stApp code { color: #FF8A5B; }
    div[data-testid="stExpander"], div[data-testid="stNotification"] {
        background-color: #1A1C24; color: #FAFAFA;
    }
</style>
"""


def apply_theme() -> None:
    """Render the sidebar dark-mode toggle and apply the theme (Requisito 2).

    A preferência vive em st.session_state["dark_mode"], que é global à sessão e,
    portanto, persiste ao navegar entre páginas.
    """
    st.session_state.setdefault("dark_mode", False)
    st.sidebar.toggle("🌙 Modo escuro", key="dark_mode")

    if st.session_state["dark_mode"]:
        st.markdown(_DARK_CSS, unsafe_allow_html=True)
