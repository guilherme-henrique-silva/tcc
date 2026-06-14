"""Página — Upload de Dados (coleta manual de links e notícias)."""

from datetime import date

import pandas as pd
import streamlit as st
from streamlit_tags import st_tags

from api_client import APIClient
from components.context import context_block
from env_config import get_date_range

st.title("📤 Upload de Dados")

context_block(
    "Por que a coleta é manual?",
    """
    Não há crawler automatizado neste projeto: por limitação técnica, **você cola os
    links** das notícias relevantes (ex.: matérias do G1, Valor, InfoMoney sobre o Banco
    do Brasil e concorrentes). O **conteúdo de cada link** é convertido em **Markdown**
    pelo Docling e segue para o tratamento e a engenharia de features. Aqui você também
    pode subir um CSV de notícias e conferir o intervalo de datas das ações (obtidas via
    yfinance).
    """,
)

client = APIClient()

tab_links, tab_csv, tab_acoes = st.tabs(["Links de Notícias", "Notícias (CSV)", "Ações"])

# --------------------------------------------------------------------------- #
# Aba 1 — Links de Notícias                                                   #
# --------------------------------------------------------------------------- #
with tab_links:
    st.subheader("Cole os links das notícias (coleta manual)")

    links = st_tags(
        label="Cole os links das notícias",
        text="Pressione Enter para adicionar",
        value=st.session_state.get("news_links", []),
        key="news_links",
    )

    if links:
        st.caption(f"{len(links)} link(s) adicionado(s).")

        if st.button("🔎 Verificar processamento (de-duplicação)"):
            for url in links:
                try:
                    existing = client.get_proc_news(url)
                except Exception as e:  # noqa: BLE001
                    st.warning(f"Não foi possível consultar '{url}': {e}")
                    continue

                if existing and existing.get("PROC_SUCCESS"):
                    st.info(
                        f"⏭️ '{url}' já processado em {existing['PROC_TS']} "
                        f"(portal: {existing.get('NM_SITE')}). Reprocessamento evitado."
                    )
                else:
                    st.success(f"🆕 '{url}' ainda não processado — será convertido.")

    # Google CSE opcional
    st.markdown("---")
    st.subheader("Google Custom Search Engine (opcional)")
    use_cse = st.checkbox(
        "Usar Google CSE para busca de notícias",
        help="Ao ativar, informe o ID do Mecanismo de Pesquisa Programável obtido em "
             "https://programmablesearchengine.google.com",
    )
    if use_cse:
        cse_id = st.text_input(
            "ID do mecanismo de pesquisa (cx)",
            placeholder="Ex.: 01234567890abcdef:example",
            key="google_cse_id",
        )
        if cse_id:
            st.caption(f"CSE configurado: `{cse_id}`")
        else:
            st.warning("Informe o ID do mecanismo de pesquisa para habilitar a busca via CSE.")

    st.info(
        "Os links ficam disponíveis na sessão e serão enviados à etapa "
        "**Transformação Docling** na página *Executar Pipeline*."
    )

# --------------------------------------------------------------------------- #
# Aba 2 — Notícias (CSV)                                                      #
# --------------------------------------------------------------------------- #
with tab_csv:
    st.subheader("Upload de Notícias (CSV)")

    st.info(
        """
        **Padrão de colunas esperado:**

        | Coluna | Tipo | Obrigatória | Observação |
        |---|---|---|---|
        | `date` | data (`YYYY-MM-DD`, `DD/MM/YYYY` ou ISO datetime) | ✅ Sim | Usada para filtrar pelo período |
        | `title` | texto | ✅ Sim | Título da notícia |
        | `content` | texto | ✅ Sim | Corpo da notícia |
        | `source` | texto | ❌ Não | Padrão: `"Unknown"` |
        | `url` | texto | ❌ Não | Padrão: vazio |
        | `sentiment` | inteiro ∈ {-1, 0, 1} | ❌ Não | -1 negativo / 0 neutro / 1 positivo |

        ⚠️ **Linhas fora deste padrão (colunas obrigatórias ausentes, datas inválidas ou
        sentimento fora de {-1, 0, 1}) serão desconsideradas pelo sistema.**
        """
    )

    uploaded_file = st.file_uploader(
        "Selecione arquivo CSV com notícias",
        type="csv",
        key="news_uploader",
    )

    if uploaded_file:
        df = pd.read_csv(uploaded_file)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Linhas", len(df))
        with col2:
            st.metric("Colunas", len(df.columns))

        st.subheader("Preview dos Dados")
        st.dataframe(df.head(10), use_container_width=True)

        st.subheader("Informações das Colunas")
        col_info = pd.DataFrame(
            {"tipo": df.dtypes, "não-nulos": df.notna().sum(), "nulos": df.isna().sum()}
        )
        st.dataframe(col_info, use_container_width=True)

        if st.button("✅ Validar Dataset"):
            try:
                result = client.validate_data(df)

                if result.get("valid"):
                    st.success("✅ Dataset válido!")
                else:
                    st.error("❌ Erros encontrados:")
                    for error in result.get("errors", []):
                        st.error(f"  • {error}")

                if result.get("warnings"):
                    st.warning("⚠️ Avisos:")
                    for warning in result.get("warnings", []):
                        st.warning(f"  • {warning}")

                if result.get("summary"):
                    st.info("📋 Resumo:")
                    for key, value in result["summary"].items():
                        st.write(f"  • {key}: {value}")

            except Exception as e:  # noqa: BLE001
                st.error(f"Erro ao validar: {e}")

        if st.button("📤 Upload para Backend"):
            try:
                file_id = client.upload_file(uploaded_file.name)
                st.success(f"✅ Arquivo salvo! ID: {file_id}")
                st.session_state.news_file_id = file_id
            except Exception as e:  # noqa: BLE001
                st.error(f"Erro ao fazer upload: {e}")

# --------------------------------------------------------------------------- #
# Aba 3 — Ações                                                                #
# --------------------------------------------------------------------------- #
with tab_acoes:
    st.info("📊 Ações serão obtidas automaticamente via yfinance (BBAS3, ITUB4, BBDC4, SANB11)")

    today = date.today()
    default_start, default_end = get_date_range()

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Data inicial",
            value=default_start,
            key="acoes_start_input",
        )
    with col2:
        raw_end = st.date_input(
            "Data final",
            value=min(default_end, today),
            max_value=today,
            key="acoes_end_input",
        )
        end_date = raw_end
        if raw_end > today:
            end_date = today
            st.warning("Data final ajustada para hoje (não é possível selecionar datas futuras).")

    # Propaga data inicial para que o sidebar aplique a restrição
    st.session_state["acoes_start_date"] = start_date

    if start_date <= end_date:
        st.success(f"Intervalo: {start_date} a {end_date}")
        st.session_state.date_range = (start_date, end_date)
    else:
        st.error("Data inicial deve ser anterior à data final.")
