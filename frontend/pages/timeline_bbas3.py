"""Página — Linha do tempo de notícias negativas de BBAS3."""

import streamlit as st
from streamlit_timeline import timeline

from components.timeline_builder import build_timeline_json
from components.context import context_block
from env_config import get_date_range

st.title("🕒 Linha do tempo — impacto negativo em BBAS3")

context_block(
    "Relação entre notícia e movimento de preço",
    """
    A timeline ajuda a inspecionar visualmente a hipótese central do trabalho: notícias
    negativas antecedem ou acompanham quedas de BBAS3. Os eventos exibidos cruzam
    **sentimento negativo** (`SentimentScore == -1`) com **queda no dia**
    (`Variacao_Pct_BBAS3 < 0`). A análise formal de defasagem (lags **T+0/T+1/T+2**) e
    causalidade fica nas etapas de features e no teste de Granger.
    """,
)

start_date, _end_date = get_date_range()

# Notícias negativas calculadas pela pipeline (etapas Docling + Engenharia de features).
# Disponibilizadas via sessão; cai num exemplo mínimo quando ausentes.
news_rows = st.session_state.get("negative_news", [])

if not news_rows:
    st.info(
        "Nenhuma notícia negativa na sessão. Execute a pipeline (etapas Docling + "
        "Engenharia de features) para popular a timeline. Exibindo um exemplo."
    )
    news_rows = [
        {
            "date": f"{start_date.year}-03-12",
            "headline": "Exemplo: notícia com impacto negativo",
            "summary": "Resumo da notícia.",
            "SentimentScore": -1,
            "Variacao_Pct_BBAS3": -1.8,
        }
    ]

timeline_json = build_timeline_json(news_rows, title_year=str(start_date.year))

if not timeline_json["events"]:
    st.warning("Nenhum evento negativo correlacionado encontrado para o período.")
else:
    timeline(timeline_json, height=800)
