"""Frontend environment configuration — datas vêm do .env, nunca de literais."""

import os
from datetime import date, datetime
from typing import Tuple

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv é opcional na imagem do frontend
    pass


# Fallback usado apenas quando o .env não define as datas.
_DEFAULT_START = datetime.now().replace(month=1, day=1).date()
_DEFAULT_END = datetime.now().replace(month=12, day=31).date()


def get_date_range() -> Tuple[date, date]:
    """Lê DATE_START/DATE_END (ISO YYYY-MM-DD) do ambiente."""
    start = _parse(os.getenv("DATE_START"), _DEFAULT_START)
    end = _parse(os.getenv("DATE_END"), _DEFAULT_END)
    return start, end


def _parse(value: str, fallback: date) -> date:
    """Parse uma data ISO, retornando o fallback se não definida."""
    if not value:
        return fallback

    return datetime.strptime(value, "%Y-%m-%d").date()


# Identificadores e rótulos das etapas (feature toggle).
STAGE_LABELS = {
    "docling_transform": "0 · Transformação Docling (links → Markdown)",
    "news_treatment": "1 · Tratamento de notícias (limpeza + frontmatter)",
    "data_collection": "2 · Coleta de mercado (ações, Ibovespa, commodities)",
    "feature_engineering": "3 · Engenharia de features (pregões da B3)",
    "confounding_handling": "4 · Controles e dataset de análise",
    "granger_causality": "5 · Causalidade de Granger (VAR)",
    "modeling_preparation": "6 · Preparação para modelagem (exploratória)",
}

# Subetapas por etapa (espelha os substages do backend).
SUBSTAGES = {
    "docling_transform": ["validar_links", "converter_markdown", "registrar_proc_news"],
    "news_treatment": ["selecionar_registros", "tratar_llm", "verificar_conformidade"],
    "data_collection": [
        "coletar_precos",
        "coletar_indice",
        "coletar_commodities",
        "consolidar_noticias",
    ],
    "feature_engineering": [
        "calendario_pregoes",
        "alinhar_noticias",
        "features_acoes",
        "features_noticias",
        "features_concorrentes",
    ],
    "confounding_handling": ["coletar_dolar", "indicador_copom", "montar_dataset"],
    "granger_causality": [
        "estacionariedade",
        "selecao_defasagens",
        "testes_granger",
        "diagnosticos",
    ],
    "modeling_preparation": [
        "dataset_nao_supervisionado",
        "dataset_supervisionado",
        "walk_forward",
    ],
}
