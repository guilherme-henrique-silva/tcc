"""Streamlit entrypoint — navegação, tema e sidebar compartilhada."""

from datetime import date

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

apply_theme()


def _render_sidebar() -> None:
    """Sidebar compartilhada: período de análise e verificação de status."""
    with st.sidebar:
        st.header("⚙️ Configuração")

        st.subheader("Período de Análise")
        _render_date_range()

        st.subheader("Status dos serviços")
        _render_status_check()


def _render_date_range() -> None:
    """Seleção de período com restrições: data inicial >= início da aba Ações."""
    default_start, default_end = get_date_range()
    today = date.today()

    # Data inicial mínima definida pela aba Ações (R3)
    acoes_start: date = st.session_state.get("acoes_start_date", default_start)

    # Datas atuais do sidebar (ou defaults)
    current_range = st.session_state.get("global_date_range", (default_start, min(default_end, today)))
    current_start = current_range[0] if isinstance(current_range, tuple) else default_start
    current_end = current_range[1] if isinstance(current_range, tuple) else min(default_end, today)

    # Forçar início para mínimo se violado
    if current_start < acoes_start:
        current_start = acoes_start
        st.warning(
            f"Data inicial ajustada para {acoes_start} "
            "(mínimo definido pela aba Ações)."
        )

    # Forçar fim para hoje se superior
    if current_end > today:
        current_end = today
        st.warning("Data final ajustada para hoje (não é possível selecionar datas futuras).")

    st.date_input(
        "Selecione o intervalo de datas",
        value=(current_start, current_end),
        min_value=acoes_start,
        max_value=today,
        key="global_date_range",
    )


def _render_status_check() -> None:
    """Botão único que reporta backend e banco; erros somem na nova tentativa."""
    backend_slot = st.empty()
    db_slot = st.empty()

    if st.button("🔄 Verificar Status"):
        backend_slot.empty()
        db_slot.empty()
        client = APIClient()
        _check_backend(client, backend_slot)
        _check_database(client, db_slot)


def _check_backend(client: APIClient, slot) -> None:
    try:
        result = client.health_check()
        slot.success(f"Backend online — {result.get('status', 'OK')}")
    except Exception as e:  # noqa: BLE001
        slot.error(f"Backend indisponível: {e}")


def _check_database(client: APIClient, slot) -> None:
    try:
        result = client.health_check_db()
        if result.get("status") == "ok":
            slot.success("Banco de dados conectado")
        else:
            slot.error(f"Banco indisponível: {result.get('reason')}")
    except Exception as e:  # noqa: BLE001
        slot.error(f"Banco indisponível: {e}")


_render_sidebar()

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
