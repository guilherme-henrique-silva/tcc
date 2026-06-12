"""Streamlit main application."""

import streamlit as st
from api_client import APIClient
from env_config import get_date_range

st.set_page_config(
    page_title="Data Pipeline - Análise de Ações e Notícias",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Pipeline de Dados para Análise de Ações")
st.markdown(
    """
    Sistema completo para análise de impacto de notícias no mercado de ações,
    com foco em BBSA3 (Banco do Brasil) e seus concorrentes.
    """
)

st.info(
    """
    **Projeto de Conclusão de Curso (TCC)** - Análise do Impacto de Notícias 
    sobre Preços de Ações usando Object Calisthenics, Arquitetura Hexagonal e Clean Code.
    """
)

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuração")
    
    st.subheader("Período de Análise")
    _default_start, _default_end = get_date_range()
    date_range = st.date_input(
        "Selecione o intervalo de datas",
        value=(_default_start, _default_end),
        key="global_date_range"
    )
    
    st.subheader("Backend Status")
    if st.button("🔄 Verificar Status"):
        with st.spinner("Conectando ao backend..."):
            try:
                client = APIClient()
                result = client.health_check()
                st.success(f"Backend online — {result.get('status', 'OK')}")
            except Exception as e:
                st.error(f"Backend indisponível: {e}")

# Main content
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Status do Backend",
        "🟢 Online",
        "Última atualização: agora"
    )

with col2:
    st.metric(
        "Checkpoints Disponíveis",
        "0",
        "Para recuperação de falhas"
    )

with col3:
    st.metric(
        "Dados Carregados",
        "0",
        "Registros em memória"
    )

st.markdown("---")

st.subheader("🚀 Próximos Passos")
st.markdown(
    """
    1. **Upload de Dados** - Carregue arquivo CSV com notícias
    2. **Executar Pipeline** - Inicie o processamento
    3. **Visualizar Features** - Analise as features calculadas
    4. **Explorar Dados** - Faça análise exploratória com plots
    """
)

st.markdown("---")

st.subheader("📖 Documentação")
with st.expander("Ver arquitetura do projeto"):
    st.markdown(
        """
        ### Estrutura
        - **Backend**: FastAPI + Arquitetura Hexagonal
        - **Frontend**: Streamlit + Pandas + Plotly
        - **Persistência**: SQLite + Checkpoints
        
        ### Fases da Pipeline
        1. **Coleta** - CSV de notícias + yfinance
        2. **Validação** - Ranges, completude, correlações
        3. **Features** - Stock, News, Competitors (2.4)
        4. **Confundidores** - Selic, USD/BRL, commodities (2.5)
        5. **Preparação** - Datasets para modelos (2.6)
        """
    )
