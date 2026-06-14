"""Página - Visualizar Features (ações, notícias e confundidores)."""

import streamlit as st
import pandas as pd
import plotly.express as px

from components.context import context_block

st.title("📊 Análise de Features")

context_block(
    "O que são estas features?",
    """
    As features traduzem os dados brutos em sinais comparáveis:

    - **Features de ações** — variação percentual diária, volatilidade (20 dias), volume
      normalizado e detecção de anomalias (>2σ).
    - **Features de notícias** — sentimento (+1/0/-1), frequência diária, TF-IDF reduzido
      e reconhecimento de entidades (banco, governo, commodity).
    - **Features + confundidores** — cruzam o sinal das notícias com Selic, dólar e
      commodities, para separar efeito de notícia de contexto macroeconômico.
    """,
)

st.info("As features serão exibidas após a pipeline ser executada com sucesso.")

tab1, tab2, tab3 = st.tabs(["Features de ações", "Features de notícias", "Features + confundidores"])

with tab1:
    st.subheader("Features de ações")
    st.write("Retorno diário, volatilidade, volume, anomalias")
    
    # Placeholder DataFrame
    df_stock = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=10),
        "ticker": "BBAS3.SA",
        "daily_return_pct": [0.5, -0.2, 1.1, -0.3, 0.8, 0.2, -0.5, 1.2, 0.3, -0.1],
        "volatility_20d": [1.2, 1.3, 1.1, 1.4, 1.2, 1.3, 1.5, 1.2, 1.1, 1.3],
    })
    
    st.dataframe(df_stock, use_container_width=True)
    
    fig = px.scatter(
        df_stock,
        x="volatility_20d",
        y="daily_return_pct",
        title="Volatilidade vs Retorno Diário",
        labels={"volatility_20d": "Volatilidade (20d)", "daily_return_pct": "Retorno Diário (%)"}
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Features de notícias")
    st.write("Sentimento, frequência, TF-IDF, entidades")
    
    df_news = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=10),
        "sentiment_score": [-1, 0, 1, 0, 1, -1, 0, 1, 1, 0],
        "news_frequency": [5, 3, 7, 2, 6, 4, 3, 8, 5, 2],
    })
    
    st.dataframe(df_news, use_container_width=True)
    
    fig = px.histogram(df_news, x="sentiment_score", title="Distribuição de Sentimento")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("Features + confundidores")
    st.write("Selic, USD/BRL, commodities")
    
    # Placeholder correlation heatmap
    st.info("Heatmap de correlação será exibido aqui")
