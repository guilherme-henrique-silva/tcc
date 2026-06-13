"""Página - Executar Pipeline (feature toggle por checkbox + stqdm + retentativa)."""

import streamlit as st
from stqdm import stqdm

from api_client import APIClient
from env_config import STAGE_LABELS, SUBSTAGES, get_date_range
from components.context import context_block

st.title("🚀 Executar Pipeline")

context_block(
    "O que cada etapa faz e por que a ordem importa",
    """
    A pipeline roda em sequência, e cada etapa alimenta a próxima:

    1. **Transformação Docling** — converte os links colados em Markdown.
    2. **Tratamento de notícias** — limpa o ruído e padroniza o frontmatter.
    3. **Coleta** — busca os preços das ações (yfinance) e consolida as notícias.
    4. **Engenharia de features** — sentimento, frequência, volatilidade, correlações (2.4).
    5. **Confundidores** — Selic, dólar e commodities + teste de Granger (2.5).
    6. **Preparação** — monta os datasets para modelagem (2.6).

    Você pode marcar/desmarcar etapas abaixo: etapas desmarcadas são puladas (SKIPPED),
    mantendo o mesmo contrato enviado ao backend.
    """,
)

client = APIClient()

# --- Seleção de etapas por checkbox (Requisito 7) --------------------------
st.subheader("Etapas a executar")
enabled = [
    key for key in STAGE_LABELS
    if st.checkbox(STAGE_LABELS[key], value=True, key=f"stage_{key}")
]

# Tratamento via LLM (Requisito 9): aplicado na etapa de tratamento de notícias.
use_llm_treatment = st.checkbox(
    "🤖 Usar LLM para tratar notícias pendentes (etapa de Tratamento)",
    value=False,
)

# Links coletados manualmente (Seção 9) — vindos da página de upload.
news_links = st.session_state.get("news_links", [])
if news_links:
    st.caption(f"🔗 {len(news_links)} link(s) de notícias na sessão.")
else:
    st.caption("ℹ️ Nenhum link de notícia na sessão (ver página *Upload de Dados*).")

start_date, end_date = get_date_range()


def _build_payload(stages: list) -> dict:
    """Monta o payload enviado ao backend (Requisitos 7 e 9)."""
    return {
        "date_range": {
            "start_date": str(start_date),
            "end_date": str(end_date),
        },
        "enabled_stages": stages,
        "news_links": news_links,
        "use_llm_treatment": use_llm_treatment,
        "treatment_model_path": st.session_state.get("treatment_model_path"),
    }


def _render_progress(stages: list, stage_results: dict) -> None:
    """Renderiza barras aninhadas etapa→subetapa com stqdm (Seção 5.1/5.2)."""
    for stage_name in stqdm(stages, desc="Pipeline"):
        substages = SUBSTAGES.get(stage_name, [])
        total = len(substages)

        for order, substage in enumerate(stqdm(substages, desc=stage_name), start=1):
            # desc com etapa · subetapa (ordem/total) — SubStageTag.label
            label = f"{stage_name} · {substage} ({order}/{total})"
            stqdm.write(label)

        status = stage_results.get(stage_name, {}).get("status", "—")
        _render_stage_status(stage_name, status, stage_results)


def _render_stage_status(stage_name: str, status: str, stage_results: dict) -> None:
    """Mostra o status de cada etapa e o botão de retentativa em caso de falha."""
    label = STAGE_LABELS.get(stage_name, stage_name)

    if status == "SUCCESS":
        st.success(f"✅ {label}")
        return

    if status == "SKIPPED":
        st.info(f"⏭️ {label} (SKIPPED)")
        return

    if status == "FAILED":
        _render_failure(stage_name, label, stage_results)
        return

    st.write(f"⏳ {label}")


def _render_failure(stage_name: str, label: str, stage_results: dict) -> None:
    """Feedback de falha com motivo + botão de retentativa (Seção 5.3/5.4)."""
    error_widget = st.empty()
    error_message = stage_results.get(stage_name, {}).get("error_message", "desconhecido")
    error_widget.error(f"❌ Falha em {label}: {error_message}")

    if st.button(f"🔁 Retentar {stage_name}", key=f"retry_{stage_name}"):
        error_widget.empty()  # apaga a mensagem de erro
        result = client.execute_pipeline(_build_payload([stage_name]))
        st.session_state.run_result = result
        st.rerun()


# --- Execução ---------------------------------------------------------------
if st.button("▶️ Iniciar Pipeline", key="execute_btn", use_container_width=True):
    if not enabled:
        st.warning("Selecione ao menos uma etapa.")
    else:
        try:
            with st.spinner("Executando pipeline..."):
                st.session_state.run_result = client.execute_pipeline(
                    _build_payload(enabled)
                )
        except Exception as e:  # noqa: BLE001
            st.error(f"❌ Erro: {e}")

st.markdown("---")

# --- Resultado --------------------------------------------------------------
result = st.session_state.get("run_result")
if result:
    st.subheader("📊 Resultado da Execução")
    st.metric("Status geral", result.get("status", "—"))

    stage_results = result.get("stage_results", {})
    executed = [s for s in STAGE_LABELS if s in stage_results]

    st.markdown("### Etapas")
    _render_progress(executed, stage_results)
