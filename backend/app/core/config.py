"""Configuration and environment settings."""

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

# Defaults portáveis derivados da localização deste arquivo
# (backend/app/core/config.py). Funcionam local e no Docker; lá as variáveis
# de ambiente são injetadas pelo docker-compose e sobrescrevem estes defaults.
_BACKEND_DIR = Path(__file__).resolve().parents[2]   # .../TCC/backend
_REPO_ROOT = _BACKEND_DIR.parent                      # .../TCC
_DEFAULT_DATA_DIR = _REPO_ROOT / "data"


class Config:
    """Application configuration."""

    # FastAPI
    APP_NAME = "Data Pipeline API"
    APP_VERSION = "1.0.0"
    API_PREFIX = "/api"

    # Database
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{_DEFAULT_DATA_DIR / 'pipeline.db'}"
    )

    # Paths
    CHECKPOINT_DIR = os.getenv(
        "CHECKPOINT_DIR",
        str(_BACKEND_DIR / "persistence" / "checkpoints")
    )
    DATA_DIR = os.getenv("DATA_DIR", str(_DEFAULT_DATA_DIR))

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # YFinance — alvo + concorrentes; índice e commodities têm variáveis próprias.
    YFINANCE_TICKERS = os.getenv(
        "YFINANCE_TICKERS",
        "BBAS3.SA,ITUB4.SA,BBDC4.SA,SANB11.SA"
    ).split(",")
    TARGET_TICKER = os.getenv("TARGET_TICKER", "BBAS3.SA").strip()
    MARKET_INDEX_TICKER = os.getenv("MARKET_INDEX_TICKER", "^BVSP").strip()
    COMMODITY_TICKERS = [
        t.strip()
        for t in os.getenv("COMMODITY_TICKERS", "ZS=F,ZC=F,LE=F").split(",")
        if t.strip()
    ]

    # Calendário de pregões e alinhamento das notícias
    # Horário de corte (Brasília, HH:MM): notícia publicada depois vai ao pregão seguinte.
    MARKET_CLOSE_TIME = os.getenv("MARKET_CLOSE_TIME", "17:00").strip()
    # Datas de anúncio das decisões do Copom (dia do comunicado, ISO, separadas por vírgula).
    # Padrão: 2025. CONFIRMAR no site do Banco Central antes de usar em produção.
    COPOM_DECISION_DATES = [
        d.strip()
        for d in os.getenv(
            "COPOM_DECISION_DATES",
            "2025-01-29,2025-03-19,2025-05-07,2025-06-18,"
            "2025-07-30,2025-09-17,2025-11-05,2025-12-10",
        ).split(",")
        if d.strip()
    ]

    # Concorrentes: "mean" (ret_peers) ou "separate" (uma coluna por ticker)
    PEERS_AGGREGATION = os.getenv("PEERS_AGGREGATION", "mean").strip().lower()

    # Teste de causalidade de Granger (VAR)
    GRANGER_MAX_LAG = int(os.getenv("GRANGER_MAX_LAG", "10"))
    GRANGER_IC = os.getenv("GRANGER_IC", "aic").strip().lower()              # aic|bic|hqic
    GRANGER_ALPHA = float(os.getenv("GRANGER_ALPHA", "0.05"))
    GRANGER_MULTITEST = os.getenv("GRANGER_MULTITEST", "holm").strip().lower()  # holm|fdr_bh
    GRANGER_NEWS_SPEC = os.getenv("GRANGER_NEWS_SPEC", "net").strip().lower()   # net|split

    # Modelo alternativo de sentimento (robustez, RF-15). Vazio = não usado.
    SENTIMENT_MODEL_ROBUSTNESS = os.getenv("SENTIMENT_MODEL_ROBUSTNESS", "").strip()

    # Date range — lido do .env, sem default fixo de ano
    DATE_START = os.getenv("DATE_START")
    DATE_END = os.getenv("DATE_END")

    # Banco Central — endpoints parametrizados por variáveis de ambiente
    API_BCB_SELIC = os.getenv("API_BCB_SELIC", "")
    API_BCB_DOLAR = os.getenv("API_BCB_DOLAR", "")
    DATA_INICIAL_SELIC = os.getenv("DATA_INICIAL_SELIC")
    DATA_FINAL_SELIC = os.getenv("DATA_FINAL_SELIC")
    DATA_INICIAL_DOLAR = os.getenv("DATA_INICIAL_DOLAR")
    DATA_FINAL_DOLAR = os.getenv("DATA_FINAL_DOLAR")

    # Feature Engineering
    VOLATILITY_WINDOW = int(os.getenv("VOLATILITY_WINDOW", "20"))
    CORRELATION_WINDOW = int(os.getenv("CORRELATION_WINDOW", "10"))
    ANOMALY_STD_THRESHOLD = float(os.getenv("ANOMALY_STD_THRESHOLD", "2.0"))
    TFIDF_COMPONENTS = int(os.getenv("TFIDF_COMPONENTS", "20"))

    # LLM — tratamento de notícias via modelo local (HF) ou API.
    LLM_BACKEND = os.getenv("LLM_BACKEND", "api")              # "local" | "api"
    LLM_MODELS_DIR = os.getenv("LLM_MODELS_DIR", str(_REPO_ROOT / "llm-models"))
    LLM_API_PROVIDER = os.getenv("LLM_API_PROVIDER", "anthropic")
    LLM_API_MODEL = os.getenv("LLM_API_MODEL", "claude-sonnet-4-6")
    # Catálogo de modelos locais (JSON), sem nomes hardcoded.
    LLM_MODELS = os.getenv("LLM_MODELS", "[]")

    @classmethod
    def llm_models(cls) -> List[Dict[str, str]]:
        """Parse o catálogo LLM_MODELS (JSON) tolerando valor ausente/inválido."""
        raw = (cls.LLM_MODELS or "").strip()
        if not raw:
            return []

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []

        if not isinstance(parsed, list):
            return []

        return [model for model in parsed if isinstance(model, dict)]

    @classmethod
    def date_range(cls) -> Tuple[date, date]:
        """Parse DATE_START/DATE_END (ISO YYYY-MM-DD) do ambiente.

        Fonte única de verdade compartilhada por backend e frontend.
        Levanta ValueError se as variáveis não estiverem definidas.
        """
        start = cls._parse_iso_date(cls.DATE_START, "DATE_START")
        end = cls._parse_iso_date(cls.DATE_END, "DATE_END")
        return start, end

    @staticmethod
    def _parse_iso_date(value: Optional[str], var_name: str) -> date:
        """Parse an ISO date string, failing loudly when missing."""
        if not value:
            raise ValueError(
                f"Environment variable {var_name} is not set (see .env)"
            )

        return datetime.strptime(value, "%Y-%m-%d").date()

    @classmethod
    def ensure_directories(cls):
        """Ensure required directories exist."""
        os.makedirs(cls.CHECKPOINT_DIR, exist_ok=True)
        os.makedirs(cls.DATA_DIR, exist_ok=True)
