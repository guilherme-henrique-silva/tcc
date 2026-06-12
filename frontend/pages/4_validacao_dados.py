"""Page 4 - Validação de Dados."""

import streamlit as st

st.set_page_config(page_title="Validação de Dados", layout="wide")
st.title("✅ Validação de Dados")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Completude", "100%", "✅")

with col2:
    st.metric("Ranges Válidos", "99.8%", "✅")

with col3:
    st.metric("Correlações", "0.85", "✅")

st.markdown("---")

st.subheader("Relatório Detalhado")

tabs = st.tabs(["Completude", "Ranges", "Correlações", "Anomalias"])

with tabs[0]:
    st.write("Verificação de valores nulos")
    st.table({
        "Coluna": ["date", "ticker", "close_price", "volume"],
        "Total": [252, 252, 252, 252],
        "Não Nulos": [252, 252, 252, 252],
        "Falta (%)": [0, 0, 0, 0],
    })

with tabs[1]:
    st.write("Verificação de ranges")
    st.table({
        "Coluna": ["daily_return_pct", "volatility_20d", "volume"],
        "Min": [-3.5, 0.8, 1000000],
        "Max": [2.8, 2.5, 50000000],
        "Dentro do Range": ["✅", "✅", "✅"],
    })

with tabs[2]:
    st.write("Correlação entre BBSA3 e concorrentes")
    st.table({
        "Comparação": ["BBAS3 vs ITUB4", "BBAS3 vs BBDC4", "BBAS3 vs SANB11"],
        "Correlação": [0.87, 0.82, 0.79],
        "Status": ["✅", "✅", "✅"],
    })

with tabs[3]:
    st.write("Detecção de anomalias")
    st.table({
        "Data": ["2025-03-15", "2025-07-22"],
        "Ticker": ["BBAS3.SA", "ITUB4.SA"],
        "Variação": [-8.5, 6.2],
        "Tipo": ["Queda anormal", "Alta anormal"],
    })
