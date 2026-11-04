"""Página — Upload de Dados (coleta manual de links e notícias)."""

from datetime import date

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_tags import st_tags

from api_client import APIClient
from components import news_links as nl
from components.context import context_block
from env_config import get_date_range

st.title("📤 Upload de Dados")

context_block(
    "Por que a coleta é manual?",
    """
    Não há crawler automatizado neste projeto: por limitação técnica, **você cola os
    links** das notícias relevantes (ex.: matérias do G1, Valor, InfoMoney sobre o Banco
    do Brasil e concorrentes), **agrupados pela data de publicação** (não pode ser futura,
    e a mesma URL só pode constar em uma data). Também é possível importar um JSON no
    formato `{"AAAA-MM-DD": ["link", ...]}`. Datas fora do período de análise geram apenas
    um aviso. O **conteúdo de cada link** é convertido em **Markdown**
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
    st.subheader("Cole os links das notícias, agrupados por data de publicação")

    # `news_links` é Dict[str, List[str]] (data ISO -> links); o widget do st_tags usa
    # outra key para não sobrescrever o dicionário da sessão.
    if not isinstance(st.session_state.get("news_links"), dict):
        st.session_state["news_links"] = {}
    st.session_state.setdefault("news_links_nonce", 0)

    groups = st.session_state["news_links"]
    today = date.today()

    col_day, col_links = st.columns([1, 3])
    with col_day:
        publication_day = st.date_input(
            "Data de publicação",
            value=today,
            max_value=today,
            key="news_links_day",
        )
    with col_links:
        typed_links = st_tags(
            label="Links publicados nesta data",
            text="Pressione Enter para adicionar",
            value=[],
            key=f"news_links_input_{st.session_state['news_links_nonce']}",
        )

    if st.button("➕ Adicionar links desta data"):
        try:
            st.session_state["news_links"] = nl.add_group(groups, publication_day, typed_links)
            st.session_state["news_links_nonce"] += 1  # novo widget => campo limpo
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    with st.expander("📥 Importar JSON (data → links)"):
        st.caption('Formato: `{"2026-11-03": ["https://...", "https://..."], "2026-11-04": ["https://..."]}`')
        json_text = st.text_area("Cole o JSON", key="news_links_json_text", height=140)
        json_file = st.file_uploader("ou envie um arquivo .json", type="json", key="news_links_json_file")

        if st.button("Importar JSON"):
            try:
                raw = json_file.getvalue().decode("utf-8") if json_file else json_text
                imported = nl.parse_json(raw)
                merged = groups
                for day, urls in imported.items():
                    merged = nl.add_group(merged, day, urls)
                st.session_state["news_links"] = merged
                st.rerun()
            except (ValueError, UnicodeDecodeError) as e:
                st.error(f"Importação recusada: {e}")  # sessão preservada

    if groups:
        total_links, total_days = nl.summary(groups)
        st.caption(f"🔗 {total_links} link(s) em {total_days} data(s).")

        range_value = st.session_state.get("date_range") or get_date_range()
        for day in nl.dates_outside(groups, range_value[0], range_value[1]):
            st.warning(
                f"📅 {nl.to_br(day)} está fora do período de análise "
                f"({range_value[0]} a {range_value[1]}); os links seguem para a pipeline."
            )

        for day in sorted(groups):
            with st.expander(f"📅 {nl.to_br(day)} · {len(groups[day])} link(s)"):
                for index, url in enumerate(groups[day]):
                    col_url, col_rm = st.columns([6, 1])
                    col_url.code(url, language=None)
                    if col_rm.button("🗑️", key=f"rm_link_{day}_{index}", help="Remover link"):
                        st.session_state["news_links"] = nl.remove_link(groups, day, url)
                        st.rerun()

                if st.button("🗑️ Remover esta data inteira", key=f"rm_day_{day}"):
                    st.session_state["news_links"] = nl.remove_group(groups, day)
                    st.rerun()

        if st.button("🔎 Verificar processamento (de-duplicação)"):
            for url in nl.flatten(groups):
                try:
                    existing = client.get_proc_news(url)
                except Exception as e:  # noqa: BLE001
                    st.warning(f"Não foi possível consultar '{url}': {e}")
                    continue

                if existing and existing.get("PROC_SUCCESS"):
                    registered = existing.get("NEWS_DATE")
                    suffix = f", data registrada: {registered}" if registered else ""
                    st.info(
                        f"⏭️ '{url}' já processado em {existing['PROC_TS']} "
                        f"(portal: {existing.get('NM_SITE')}{suffix}). Reprocessamento evitado."
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
            components.html(
                f"""
                <script async src="https://cse.google.com/cse.js?cx={cse_id}"></script>
                <div class="gcse-search"></div>
                """,
                height=600,
            )
        else:
            st.warning("Informe o ID do mecanismo de pesquisa para habilitar a busca via CSE.")

    st.info(
        "Os links ficam na sessão, **agrupados por data de publicação**, e serão enviados à "
        "etapa **Transformação Docling** na página *Executar Pipeline*. A data informada "
        "acompanha cada notícia até a coleta (vale como data de publicação quando o "
        "tratamento não extrair uma)."
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
        | `url` | texto | ✅ Sim | Chave primária do registro; linhas sem `url` são descartadas |
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
