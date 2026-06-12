"""Page 5 - Análise Exploratória."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="Análise Exploratória", layout="wide")
st.title("📈 Análise Exploratória de Dados (EDA)")

# Generate sample data
date_range = pd.date_range("2025-01-01", periods=252)
np.random.seed(42)

df_eda = pd.DataFrame({
    "date": date_range,
    "BBAS3": np.cumsum(np.random.randn(252) * 0.5) + 100,
    "ITUB4": np.cumsum(np.random.randn(252) * 0.5) + 100,
    "BBDC4": np.cumsum(np.random.randn(252) * 0.5) + 100,
    "SANB11": np.cumsum(np.random.randn(252) * 0.5) + 100,
})

st.subheader("Série Temporal de Preços")

fig = px.line(
    df_eda.melt(id_vars=["date"], var_name="Ticker", value_name="Preço"),
    x="date",
    y="Preço",
    color="Ticker",
    title="Evolução de Preços - 2025",
)
st.plotly_chart(fig, use_container_width=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Distribuição de Retornos")
    df_returns = df_eda[["BBAS3", "ITUB4", "BBDC4", "SANB11"]].pct_change() * 100
    
    fig = px.histogram(
        df_returns.melt(var_name="Ticker", value_name="Retorno (%)"),
        x="Retorno (%)",
        color="Ticker",
        title="Distribuição de Retornos Diários",
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Matriz de Correlação")
    corr_matrix = df_eda[["BBAS3", "ITUB4", "BBDC4", "SANB11"]].corr()
    
    fig = px.imshow(
        corr_matrix,
        labels=dict(x="Ticker", y="Ticker", color="Correlação"),
        title="Correlação Entre Preços",
        color_continuous_scale="RdBu",
        zmin=-1,
        zmax=1,
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

st.subheader("Estatísticas Descritivas")
st.dataframe(df_eda[["BBAS3", "ITUB4", "BBDC4", "SANB11"]].describe(), use_container_width=True)
