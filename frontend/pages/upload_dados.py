"""Página - Upload de Dados (coleta manual de links e notícias)."""

import streamlit as st
import pandas as pd
from streamlit_tags import st_tags
from api_client import APIClient
from components.context import context_block

st.title("📤 Upload de Dados")

context_block(
    "Por que a coleta é manual?",
    """
    Não há crawler automatizado neste projeto: por limitação técnica, **você cola os
    links** das notícias relevantes (ex.: matérias do G1, Valor, InfoMoney sobre o Banco
    do Brasil e concorrentes). Cada link é depois convertido em **Markdown** pelo Docling
    e segue para o tratamento e a engenharia de features. Aqui você também pode subir um
    CSV de notícias e conferir o intervalo de datas das ações (obtidas via yfinance).
    """,
)

client = APIClient()

tab_links, tab1, tab2 = st.tabs(["Links de Notícias", "Notícias (CSV)", "Ações"])

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

    st.info(
        "Os links ficam disponíveis na sessão e serão enviados à etapa "
        "**Transformação Docling** na página *Executar Pipeline*."
    )

with tab1:
    st.subheader("Upload de Notícias (CSV)")
    
    uploaded_file = st.file_uploader(
        "Selecione arquivo CSV com notícias",
        type="csv",
        key="news_uploader"
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
        st.dataframe(df.info(), use_container_width=True)
        
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
            
            except Exception as e:
                st.error(f"Erro ao validar: {str(e)}")
        
        if st.button("📤 Upload para Backend"):
            try:
                file_id = client.upload_file(uploaded_file.name)
                st.success(f"✅ Arquivo salvo! ID: {file_id}")
                st.session_state.news_file_id = file_id
            except Exception as e:
                st.error(f"Erro ao fazer upload: {str(e)}")

with tab2:
    st.info("📊 Ações serão obtidas automaticamente via yfinance (BBAS3, ITUB4, BBDC4, SANB11)")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Data inicial")
    with col2:
        end_date = st.date_input("Data final")
    
    if start_date <= end_date:
        st.success(f"Intervalo: {start_date} a {end_date}")
        st.session_state.date_range = (start_date, end_date)
    else:
        st.error("Data inicial deve ser anterior à data final")
