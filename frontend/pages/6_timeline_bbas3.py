"""Page 6 - Timeline de notícias negativas de BBAS3 (Seção 9 do spec)."""

import streamlit as st
from streamlit_timeline import timeline

from components.timeline_builder import build_timeline_json
from env_config import get_date_range

st.set_page_config(page_title="Timeline BBAS3", layout="wide")
st.title("🕒 Linha do tempo — impacto negativo em BBAS3")

st.markdown(
    """
    Eventos selecionados: notícias com **sentimento negativo**
    (`SentimentScore == -1`) coincidentes com **queda** de BBAS3 no dia
    (`Variacao_Pct_BBAS3 < 0`).
    """
)

start_date, _end_date = get_date_range()

# Notícias negativas calculadas pela pipeline (etapa Docling + features 2.4).
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
