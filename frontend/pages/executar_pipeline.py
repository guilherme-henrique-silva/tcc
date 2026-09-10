"""Página — Executar Pipeline."""

import streamlit as st
from stqdm import stqdm

from api_client import APIClient
from env_config import STAGE_LABELS, SUBSTAGES, get_date_range
from components.context import context_block

st.title("🚀 Executar Pipeline")

context_block(
    "O que cada etapa faz e por que a ordem importa",
    """
    A pipeline roda em sequência: cada etapa entrega dados para a seguinte. Marque ou
    desmarque etapas abaixo. **Etapas com fundo cinza são obrigatórias** para a continuidade
    lógica da pipeline e não podem ser desativadas enquanto suas dependentes estiverem marcadas.
    Etapas opcionais podem ser puladas — o backend registra o status `SKIPPED` e segue adiante.

    ---
    **0 · Transformação Docling** *(opcional)*
    Converte o **conteúdo** de cada link colado na tela de Upload em texto Markdown estruturado,
    usando a biblioteca Docling. Esse Markdown bruto é a matéria-prima para o tratamento
    e a extração de features de texto. Se não houver links novos, esta etapa pode ser pulada.

    **1 · Tratamento de notícias** *(opcional — depende da etapa 0)*
    Limpa o ruído da página original (menus, rodapés, banners) e padroniza um cabeçalho
    de metadados (`title`, `subtitle`, `url`, `date`) em cada notícia. O tratamento pode
    ser feito via LLM ou manualmente na tela **Tratamento de Notícias** antes ou depois
    da execução. Pode ser pulada se as notícias já estiverem tratadas.

    **2 · Coleta de preços** *(obrigatória)*
    Busca via yfinance os preços históricos diários de BBAS3, ITUB4, BBDC4 e SANB11
    para o período selecionado no sidebar, e consolida as notícias já processadas.
    Esta etapa é a base para toda a engenharia de features.

    **3 · Engenharia de features** *(obrigatória — depende da etapa 2)*
    Calcula variáveis numéricas a partir dos dados brutos: variação percentual e
    volatilidade das ações (desvio padrão móvel de 20 dias), sentimento e frequência
    diária das notícias, TF-IDF, reconhecimento de entidades e correlação móvel de 10
    dias com concorrentes.

    **4 · Confundidores macroeconômicos** *(opcional)*
    Coleta taxa Selic, cotação USD/BRL e commodities agrícolas via API do Banco Central
    e aplica o Teste de Causalidade de Granger (p < 0,05). Essas variáveis de controle
    separam o efeito das notícias de movimentos macroeconômicos sistêmicos. Pode ser
    pulada se o foco for apenas nas features de notícias e ações.

    **5 · Preparação para modelagem** *(obrigatória — depende das etapas 2 e 3)*
    Monta os datasets finais: não supervisionado (para clustering/PCA), supervisionado
    (para regressão/classificação) e os splits de walk-forward validation, garantindo
    que o treino não "veja" dados futuros.
    """,
)

client = APIClient()

# --------------------------------------------------------------------------- #
# Seleção de etapas com dependências                                           #
# --------------------------------------------------------------------------- #
st.subheader("Etapas a executar")
st.caption(
    "Etapas marcadas serão executadas; as desmarcadas ficam com status SKIPPED. "
    "Etapas obrigatórias ficam desabilitadas se dependentes estiverem marcadas."
)

# Mapa de pré-requisitos obrigatórios (chave = etapa, valor = pré-req)
_REQUIRES: dict[str, str] = {
    "news_treatment": "docling_transform",
    "feature_engineering": "data_collection",
    "modeling_preparation": "feature_engineering",
}

# Etapas obrigatórias (não podem ser desmarcadas)
_MANDATORY = {"data_collection", "feature_engineering", "modeling_preparation"}

stage_states: dict[str, bool] = {}
for key, label in STAGE_LABELS.items():
    prereq = _REQUIRES.get(key)
    # Desabilita se pré-requisito existir e estiver desmarcado
    disabled = prereq is not None and not stage_states.get(prereq, True)
    # Etapas obrigatórias ficam sempre marcadas
    forced_on = key in _MANDATORY

    if forced_on:
        st.checkbox(label, value=True, disabled=True, key=f"stage_{key}")
        stage_states[key] = True
    else:
        checked = st.checkbox(label, value=True, disabled=disabled, key=f"stage_{key}")
        stage_states[key] = checked if not disabled else False

enabled = [key for key, active in stage_states.items() if active]

# --------------------------------------------------------------------------- #
# Configuração de auto-tratamento via LLM                                      #
# --------------------------------------------------------------------------- #
_treatment_enabled = stage_states.get("news_treatment", False)

if _treatment_enabled:
    use_llm_auto = st.checkbox(
        "🤖 Tratar automaticamente via LLM as notícias ainda não tratadas",
        value=False,
        help=(
            "Quando ativo, a pipeline envia cada notícia pendente para o modelo selecionado "
            "na tela **Tratamento de Notícias**. Notícias já tratadas são reutilizadas sem "
            "novo processamento."
        ),
    )
    if use_llm_auto:
        model_path = st.session_state.get("treatment_model_path")
        if model_path:
            st.caption(f"📦 Modelo: `{model_path}`")
        else:
            st.warning(
                "Nenhum modelo selecionado. Acesse **Tratamento de Notícias** e escolha um "
                "modelo local antes de executar."
            )
else:
    use_llm_auto = False

# Links coletados manualmente — vindos da página de upload.
news_links = st.session_state.get("news_links", [])
if news_links:
    st.caption(f"🔗 {len(news_links)} link(s) de notícias na sessão.")
else:
    st.caption("ℹ️ Nenhum link de notícia na sessão (ver página *Upload de Dados*).")

start_date, end_date = get_date_range()


def _build_payload(stages: list, discarded: list | None = None) -> dict:
    return {
        "date_range": {
            "start_date": str(start_date),
            "end_date": str(end_date),
        },
        "enabled_stages": stages,
        "news_links": news_links,
        "use_llm_treatment": use_llm_auto and _treatment_enabled,
        "treatment_model_path": st.session_state.get("treatment_model_path"),
        "discarded_news_urls": discarded or [],
    }


def _render_progress(stages: list, stage_results: dict) -> None:
    for stage_name in stqdm(stages, desc="Pipeline"):
        substages = SUBSTAGES.get(stage_name, [])
        total = len(substages)

        for order, substage in enumerate(stqdm(substages, desc=stage_name), start=1):
            label = f"{stage_name} · {substage} ({order}/{total})"
            stqdm.write(label)

        status = stage_results.get(stage_name, {}).get("status", "—")
        _render_stage_status(stage_name, status, stage_results)


def _render_stage_status(stage_name: str, status: str, stage_results: dict) -> None:
    label = STAGE_LABELS.get(stage_name, stage_name)

    if status == "SUCCESS":
        st.success(f"✅ {label}")
        return

    if status == "SKIPPED":
        st.info(f"⏭️ {label} (SKIPPED)")
        return

    if status == "BLOCKED":
        st.warning(f"⏸️ {label} (aguardando tratamento)")
        return

    if status == "FAILED":
        _render_failure(stage_name, label, stage_results)
        return

    st.write(f"⏳ {label}")


def _render_failure(stage_name: str, label: str, stage_results: dict) -> None:
    error_widget = st.empty()
    error_message = stage_results.get(stage_name, {}).get("error_message", "desconhecido")
    error_widget.error(f"❌ Falha em {label}: {error_message}")

    if st.button(f"🔁 Retentar {stage_name}", key=f"retry_{stage_name}"):
        error_widget.empty()
        result = client.execute_pipeline(_build_payload([stage_name]))
        st.session_state.run_result = result
        st.rerun()


def _render_blocked(result: dict) -> None:
    """Exibe registros pendentes e oferece as duas opções de resolução."""
    pending_urls = result.get("pending_treatment_urls") or []

    st.warning(
        f"⏸️ **Pipeline pausada** — {len(pending_urls)} notícia(s) aguardam tratamento "
        "antes de prosseguir."
    )

    with st.expander("Ver URLs pendentes", expanded=True):
        for url in pending_urls:
            st.code(url, language=None)

    st.markdown("**Como prosseguir:**")
    col_tratar, col_descartar = st.columns(2)

    with col_tratar:
        st.info(
            "**Tratar os pendentes** — acesse a tela **Tratamento de Notícias**, conclua o "
            "tratamento (manual ou LLM) e execute a pipeline novamente."
        )
        if st.button("📄 Ir para Tratamento de Notícias", use_container_width=True):
            st.switch_page("pages/tratamento_noticias.py")

    with col_descartar:
        st.warning(
            "**Descartar e avançar** — exclui os pendentes desta execução e prossegue "
            "apenas com as notícias já tratadas. O Markdown bruto **não é apagado**."
        )
        if st.button(
            f"🗑️ Descartar {len(pending_urls)} pendente(s) e avançar",
            use_container_width=True,
            type="primary",
        ):
            try:
                with st.spinner("Executando pipeline sem os pendentes..."):
                    new_result = client.execute_pipeline(
                        _build_payload(enabled, discarded=pending_urls)
                    )
                    st.session_state.run_result = new_result
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"❌ Erro: {e}")


# --------------------------------------------------------------------------- #
# Execução                                                                     #
# --------------------------------------------------------------------------- #
if st.button("▶️ Iniciar Pipeline", key="execute_btn", use_container_width=True):
    if not enabled:
        st.warning("Selecione ao menos uma etapa.")
    else:
        try:
            with st.spinner("Executando pipeline..."):
                result = client.execute_pipeline(_build_payload(enabled))
                st.session_state.run_result = result

            pipeline_id = result.get("pipeline_id")
            if pipeline_id:
                st.success(f"✅ Execução concluída — ID: `{pipeline_id}`")

        except Exception as e:  # noqa: BLE001
            st.error(f"❌ Erro: {e}")

st.markdown("---")

# --------------------------------------------------------------------------- #
# Resultado                                                                    #
# --------------------------------------------------------------------------- #
result = st.session_state.get("run_result")
if result:
    overall_status = result.get("status", "—")

    if overall_status == "BLOCKED":
        _render_blocked(result)
    else:
        st.subheader("📊 Resultado da Execução")

        pipeline_id = result.get("pipeline_id")
        if pipeline_id:
            st.code(f"ID da execução: {pipeline_id}", language=None)

        st.metric("Status geral", overall_status)

        stage_results = result.get("stage_results", {})
        executed = [s for s in STAGE_LABELS if s in stage_results]

        st.markdown("### Etapas")
        _render_progress(executed, stage_results)
