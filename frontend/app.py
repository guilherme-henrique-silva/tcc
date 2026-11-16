"""Streamlit entrypoint — navegação, tema e sidebar compartilhada."""

from datetime import date

import streamlit as st

from api_client import APIClient, api_error_message
from env_config import get_date_range
from components import run_restore as rr
from components.theme import apply_theme

st.set_page_config(
    page_title="Data Pipeline - Análise de Ações e Notícias",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()


def _render_sidebar() -> None:
    """Sidebar compartilhada: execução carregada, período de análise e status."""
    with st.sidebar:
        st.header("⚙️ Configuração")

        st.subheader("Execução carregada")
        _render_run_restore()

        st.subheader("Período de Análise")
        _render_date_range()

        st.subheader("Status dos serviços")
        _render_status_check()


def _restore_latest_run_once() -> None:
    """Na primeira renderização da sessão, recarrega a execução mais recente do backend.

    Sem isso, reiniciar os serviços deixa a sessão vazia mesmo com tudo salvo no banco.
    Roda antes da sidebar para que o período restaurado entre no seletor de datas. Falha
    de conexão não bloqueia a UI: o aviso aparece na sidebar e há o botão de recarga.
    """
    if st.session_state.get("run_restore_attempted"):
        return

    st.session_state["run_restore_attempted"] = True

    try:
        state = APIClient().get_latest_run()
    except Exception as e:  # noqa: BLE001
        st.session_state["run_restore_notice"] = (
            "warning", f"Não foi possível recarregar a última execução: {api_error_message(e)}"
        )
        return

    if state:
        rr.apply_to_session(st.session_state, state)


def _load_run(proc_id: str) -> None:
    """Callback do botão: recarrega a execução escolhida (roda antes do rerun, então pode
    alterar também o estado de widgets, como o seletor de período)."""
    try:
        state = APIClient().get_run(proc_id)
    except Exception as e:  # noqa: BLE001
        st.session_state["run_restore_notice"] = (
            "error", f"Não foi possível carregar a execução: {api_error_message(e)}"
        )
        return

    rr.apply_to_session(st.session_state, state)
    st.session_state["run_restore_notice"] = ("success", "Execução carregada.")


def _refresh_runs_list() -> None:
    """Callback do botão: consulta o histórico de execuções no backend."""
    try:
        st.session_state["runs_list"] = APIClient().list_runs()
    except Exception as e:  # noqa: BLE001
        st.session_state["run_restore_notice"] = (
            "error", f"Não foi possível listar as execuções: {api_error_message(e)}"
        )


def _render_run_restore() -> None:
    """Mostra a execução carregada e permite escolher outra do histórico."""
    notice = st.session_state.pop("run_restore_notice", None)
    if notice:
        getattr(st, notice[0])(notice[1])

    loaded = st.session_state.get(rr.LOADED_RUN_KEY)
    if loaded:
        st.caption(rr.describe(loaded))
    else:
        st.caption("Nenhuma execução carregada — a sessão começa vazia.")

    with st.expander("📂 Execuções anteriores"):
        st.button("🔄 Listar execuções", on_click=_refresh_runs_list, key="list_runs_btn")

        runs = st.session_state.get("runs_list") or []
        if not runs:
            st.caption("Clique em *Listar execuções* para consultar o histórico.")
            return

        by_id = {run["proc_id"]: run for run in runs}
        chosen = st.selectbox(
            "Execução",
            options=list(by_id),
            format_func=lambda proc_id: rr.run_label(by_id[proc_id]),
            key="run_restore_choice",
        )
        st.button(
            "📥 Carregar execução",
            on_click=_load_run,
            args=(chosen,),
            key="load_run_btn",
            use_container_width=True,
        )


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

    # `value` só na 1ª renderização: com a chave já no estado (inclusive quando a recarga de
    # uma execução a preenche) passar `value` dispara o aviso do Streamlit.
    initial = {} if "global_date_range" in st.session_state else {"value": (current_start, current_end)}

    st.date_input(
        "Selecione o intervalo de datas",
        min_value=acoes_start,
        max_value=today,
        key="global_date_range",
        **initial,
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


_restore_latest_run_once()
_render_sidebar()

pages = [
    st.Page("pages/inicio.py", title="Início", icon="🏠", default=True),
    st.Page("pages/upload_dados.py", title="1 · Upload de Dados", icon="📤"),
    st.Page("pages/executar_pipeline.py", title="2 · Executar Pipeline", icon="🚀"),
    st.Page("pages/tratamento_noticias.py", title="3 · Tratamento de Notícias", icon="🧹"),
    st.Page("pages/visualizar_features.py", title="4 · Visualizar Features", icon="📊"),
    st.Page("pages/causalidade_granger.py", title="5 · Causalidade de Granger", icon="🔗"),
    st.Page("pages/validacao_dados.py", title="6 · Validação de Dados", icon="✅"),
    st.Page("pages/analise_exploratoria.py", title="7 · Análise Exploratória", icon="📈"),
    st.Page("pages/timeline_bbas3.py", title="8 · Timeline BBAS3", icon="🕒"),
]

st.navigation(pages).run()
