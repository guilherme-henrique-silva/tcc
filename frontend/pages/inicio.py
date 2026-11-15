"""Página - Início (visão geral do projeto e próximos passos)."""

import streamlit as st

from components.context import context_block

st.title("📊 Pipeline de Dados para Análise de Ações")

st.markdown(
    """
    Sistema para análise da relação preditiva entre notícias e o mercado de ações, com foco em
    **BBAS3 (Banco do Brasil)** e seus concorrentes (ITUB4, BBDC4, SANB11).
    """
)

context_block(
    "Sobre este projeto (TCC)",
    """
    Trabalho de Conclusão de Curso que investiga se as notícias **antecedem** (têm
    informação preditiva sobre) o retorno da ação do Banco do Brasil, por meio do teste de
    causalidade de Granger. A coleta de notícias é **manual** (você cola os links); o
    restante é automatizado pela pipeline. A arquitetura segue **Hexagonal (Ports & Adapters)**,
    **Clean Code** e **Object Calisthenics**.
    """,
)

st.markdown("---")

st.subheader("🚀 Próximos passos")
st.markdown(
    """
    1. **Upload de Dados** — cole os links das notícias (e, opcionalmente, suba um CSV).
    2. **Executar Pipeline** — escolha as etapas e inicie o processamento.
    3. **Tratamento de Notícias** — limpe o conteúdo (manual ou via LLM) e valide lado a lado.
    4. **Visualizar Features / Causalidade de Granger / Validação / Análise** — explore os
       resultados.
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

        ### Etapas da Pipeline
        1. **Transformação Docling** — links → Markdown
        2. **Tratamento de notícias** — limpeza + frontmatter (manual/LLM)
        3. **Coleta** — ações, Ibovespa e futuros de commodities (yfinance) + consolidação de notícias
        4. **Engenharia de features** — calendário de pregões da B3, alinhamento das notícias
           ao pregão, retorno logarítmico, Sₜ, Nₜ, Dₜ e concorrentes
        5. **Controles** — Ibovespa, concorrentes, USD/BRL, commodities e Copom (sem filtro
           por p-valor) → dataset de análise
        6. **Causalidade de Granger** — VAR com ADF/KPSS, Toda-Yamamoto, diagnósticos e
           correção de Holm/BH (causalidade **preditiva**, não estrutural)
        7. **Preparação** — datasets exploratórios para modelagem
        """
    )

st.markdown("---")

st.caption(
    "Desenvolvido por Guilherme Henrique da Silva - TCC Univesp 2026 | " +
    "🔗 Repositório no [GitHub](https://github.com/guilherme-henrique-silva/tcc-univesp-2026)"
)
