"""Page 3 - Visualizar Features."""

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Visualizar Features", layout="wide")
st.title("📊 Análise de Features")

st.info("Features serão exibidas após a pipeline ser executada com sucesso")

tab1, tab2, tab3 = st.tabs(["Stock Features", "News Features", "Features + Confundidores"])

with tab1:
    st.subheader("Stock Features")
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
    st.subheader("News Features")
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
    st.subheader("Features + Confundidores")
    st.write("Selic, USD/BRL, commodities")
    
    # Placeholder correlation heatmap
    st.info("Heatmap de correlação será exibido aqui")
