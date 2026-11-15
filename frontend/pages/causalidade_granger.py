"""Página — Causalidade de Granger (relatório da última execução, lido de `granger_results`)."""

import streamlit as st

from api_client import APIClient, api_error_message
from components import granger_report as gr
from components.context import context_block

st.title("🔗 Causalidade de Granger")

context_block(
    "Como ler este relatório",
    """
    O teste de Granger é feito em um **VAR** com o log-retorno da BBAS3, o sentimento
    líquido (Sₜ), o volume (Nₜ) e a presença de notícias (Dₜ), condicionado a **controles
    fixos** — Ibovespa, concorrentes, variação do USD/BRL e commodities —, mais o indicador
    do Copom. Os controles **não passam por filtro de p-valor**.

    A defasagem vem de AIC/BIC (até 10 pregões); se há série integrada, usa-se
    **Toda-Yamamoto**. Os p-valores da família principal (quatro sentidos) recebem
    correção de **Holm** (decisão) e **Benjamini-Hochberg** (informativa).

    ⚠️ O resultado é **causalidade preditiva** (precedência temporal), **não** causalidade
    estrutural. *Não rejeitar H₀ não prova ausência de relação.* Esta página só **lê** o
    relatório salvo; nada é recalculado aqui.
    """,
)

client = APIClient()

default_id = st.session_state.get("run_result", {}).get("pipeline_id", "")
proc_id = st.text_input(
    "ID da execução (vazio = última execução com relatório)",
    value=default_id,
    key="granger_proc_id",
)

try:
    response = client.get_granger_report(proc_id.strip() or None)
except Exception as e:  # noqa: BLE001
    st.error(f"❌ Não foi possível ler o relatório: {api_error_message(e)}")
    st.stop()

report = response.get("report")
if not report:
    st.info(
        "Nenhum relatório de Granger encontrado. Execute a pipeline com a etapa "
        "**5 · Causalidade de Granger** habilitada na página *Executar Pipeline*."
    )
    st.stop()

st.caption(f"Execução: `{response.get('proc_id') or '—'}`")

columns = st.columns(5)
for column, (label, value) in zip(columns, gr.summary_metrics(report).items()):
    column.metric(label, value)

st.caption(gr.model_description(report))

if report.get("warnings"):
    with st.expander(f"⚠️ Avisos e premissas ({len(report['warnings'])})", expanded=True):
        for warning in report["warnings"]:
            st.warning(warning)

NUMBER_FORMAT = {
    "F": "{:.3f}", "p bruto": "{:.4f}", "p robusto": "{:.4f}",
    "p ajustado": "{:.4f}", "p BH": "{:.4f}",
}

st.subheader("Família principal — quatro sentidos")
st.caption(gr.TEST_ORDER_HELP)
main = gr.tests_frame(report, "principal")
if main.empty:
    st.info("O relatório não traz testes do modelo principal.")
else:
    st.dataframe(main.style.format(NUMBER_FORMAT, na_rep="—"), use_container_width=True)

robustness = [m for m in gr.models_in(report) if m != "principal"]
if robustness:
    st.subheader("Robustez")
    st.caption("Modelos separados; ficam **fora** da família principal e da sua correção.")
    for model in robustness:
        with st.expander(gr.MODEL_LABELS[model]):
            st.dataframe(
                gr.tests_frame(report, model).style.format(NUMBER_FORMAT, na_rep="—"),
                use_container_width=True,
            )

left, right = st.columns(2)
with left:
    st.subheader("Estacionariedade")
    st.caption("ADF (H₀: raiz unitária) e KPSS (H₀: estacionária).")
    stationarity = gr.stationarity_frame(report)
    if not stationarity.empty:
        st.dataframe(
            stationarity.style.format(
                {c: "{:.4f}" for c in stationarity.columns if c not in ("Variável", "Classificação")},
                na_rep="—",
            ),
            use_container_width=True,
        )
with right:
    st.subheader("Defasagem por critério")
    lags = gr.lag_frame(report)
    if lags.empty:
        st.info("Seleção de defasagem não realizada.")
    else:
        st.dataframe(lags, use_container_width=True, hide_index=True)

st.subheader("Diagnósticos")
diagnostics = gr.diagnostics_frame(report)
if diagnostics.empty:
    st.info("Sem diagnósticos disponíveis.")
else:
    st.dataframe(diagnostics.style.format({"p-valor": "{:.4f}"}, na_rep="—"),
                 use_container_width=True, hide_index=True)

st.subheader("Auditoria do alinhamento notícia → pregão")
audit = gr.audit_frame(report)
if audit.empty:
    st.info("Sem auditoria de alinhamento no relatório.")
else:
    st.dataframe(audit, use_container_width=True, hide_index=True)
