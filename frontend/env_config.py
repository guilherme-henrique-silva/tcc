"""Frontend environment configuration (Seção 7: datas vêm do .env, nunca de literais)."""

import os
from datetime import date, datetime
from typing import Tuple

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional in the frontend image
    pass


# Fallback usado apenas quando o .env não define as datas (nunca um ano literal no código).
_DEFAULT_START = datetime.now().replace(month=1, day=1).date()
_DEFAULT_END = datetime.now().replace(month=12, day=31).date()


def get_date_range() -> Tuple[date, date]:
    """Read DATE_START/DATE_END (ISO YYYY-MM-DD) from the environment."""
    start = _parse(os.getenv("DATE_START"), _DEFAULT_START)
    end = _parse(os.getenv("DATE_END"), _DEFAULT_END)
    return start, end


def _parse(value: str, fallback: date) -> date:
    """Parse an ISO date, falling back to the current-year boundary if unset."""
    if not value:
        return fallback

    return datetime.strptime(value, "%Y-%m-%d").date()


# Identificadores e rótulos das etapas (feature toggle, Seção 4 do spec).
STAGE_LABELS = {
    "docling_transform": "0 · Transformação Docling (links → Markdown)",
    "data_collection": "1 · Coleta de preços (yfinance)",
    "feature_engineering": "2 · Engenharia de features (2.4)",
    "confounding_handling": "3 · Confundidores macro (2.5)",
    "modeling_preparation": "4 · Preparação para modelagem (2.6)",
}

# Subetapas por etapa (espelha PipelineStage.substages no backend, Seção 3/5).
SUBSTAGES = {
    "docling_transform": ["validar_links", "converter_markdown", "registrar_proc_news"],
    "data_collection": ["coletar_precos", "consolidar_noticias"],
    "feature_engineering": ["features_acoes", "features_noticias", "features_concorrentes"],
    "confounding_handling": [
        "coletar_selic",
        "coletar_dolar",
        "coletar_commodities",
        "teste_granger",
    ],
    "modeling_preparation": [
        "dataset_nao_supervisionado",
        "dataset_supervisionado",
        "walk_forward",
    ],
}
