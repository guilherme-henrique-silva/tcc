"""Streamlit entrypoint - navegação, tema e sidebar compartilhada (Requisitos 2, 3, 6)."""

import streamlit as st

from api_client import APIClient
from env_config import get_date_range
from components.theme import apply_theme

st.set_page_config(
    page_title="Data Pipeline - Análise de Ações e Notícias",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Tema claro/escuro alternável e persistente entre páginas (Requisito 2).
apply_theme()


def _render_sidebar() -> None:
    """Sidebar compartilhada: período de análise e verificação de status (Requisitos 5/6)."""
    with st.sidebar:
        st.header("⚙️ Configuração")

        st.subheader("Período de Análise")
        default_start, default_end = get_date_range()
        st.date_input(
            "Selecione o intervalo de datas",
            value=(default_start, default_end),
            key="global_date_range",
        )

        st.subheader("Status dos serviços")
        _render_status_check()


def _render_status_check() -> None:
    """Botão único que reporta backend e banco; erros somem na nova tentativa (Requisito 6)."""
    backend_slot = st.empty()
    db_slot = st.empty()

    if st.button("🔄 Verificar Status"):
        backend_slot.empty()
        db_slot.empty()
        client = APIClient()
        _check_backend(client, backend_slot)
        _check_database(client, db_slot)


def _check_backend(client: APIClient, slot) -> None:
    """Report backend connectivity in its placeholder (Requisito 6)."""
    try:
        result = client.health_check()
        slot.success(f"Backend online — {result.get('status', 'OK')}")
    except Exception as e:  # noqa: BLE001
        slot.error(f"Backend indisponível: {e}")


def _check_database(client: APIClient, slot) -> None:
    """Report database connectivity, citing the reason on failure (Requisito 6)."""
    try:
        result = client.health_check_db()
        if result.get("status") == "ok":
            slot.success("Banco de dados conectado")
        else:
            slot.error(f"Banco indisponível: {result.get('reason')}")
    except Exception as e:  # noqa: BLE001
        slot.error(f"Banco indisponível: {e}")


_render_sidebar()

# Navegação com rótulos numerados; arquivos sem prefixo numérico (Requisito 3).
pages = [
    st.Page("pages/inicio.py", title="Início", icon="🏠", default=True),
    st.Page("pages/upload_dados.py", title="1 · Upload de Dados", icon="📤"),
    st.Page("pages/executar_pipeline.py", title="2 · Executar Pipeline", icon="🚀"),
    st.Page("pages/tratamento_noticias.py", title="3 · Tratamento de Notícias", icon="🧹"),
    st.Page("pages/visualizar_features.py", title="4 · Visualizar Features", icon="📊"),
    st.Page("pages/validacao_dados.py", title="5 · Validação de Dados", icon="✅"),
    st.Page("pages/analise_exploratoria.py", title="6 · Análise Exploratória", icon="📈"),
    st.Page("pages/timeline_bbas3.py", title="7 · Timeline BBAS3", icon="🕒"),
]

st.navigation(pages).run()
