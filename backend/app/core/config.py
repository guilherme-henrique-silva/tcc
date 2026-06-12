"""Configuration and environment settings."""

import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple

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

    # YFinance
    YFINANCE_TICKERS = os.getenv(
        "YFINANCE_TICKERS",
        "BBAS3.SA,ITUB4.SA,BBDC4.SA,SANB11.SA"
    ).split(",")

    # Date range (Seção 7: lido do .env, sem default fixo de ano)
    DATE_START = os.getenv("DATE_START")
    DATE_END = os.getenv("DATE_END")

    # Banco Central (Seção 6): endpoints parametrizados por variáveis de ambiente
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

    @classmethod
    def date_range(cls) -> Tuple[date, date]:
        """Parse DATE_START/DATE_END (ISO `YYYY-MM-DD`) from the environment.

        Single source of truth shared by backend and frontend (Seção 7 do spec).
        Raises ValueError if the variables are not defined.
        """
        start = cls._parse_iso_date(cls.DATE_START, "DATE_START")
        end = cls._parse_iso_date(cls.DATE_END, "DATE_END")
        return start, end

    @staticmethod
    def _parse_iso_date(value: Optional[str], var_name: str) -> date:
        """Parse an ISO date string, failing loudly when missing (Rule 1)."""
        if not value:
            raise ValueError(
                f"Environment variable {var_name} is not set (see .env / Seção 7)"
            )

        return datetime.strptime(value, "%Y-%m-%d").date()

    @classmethod
    def ensure_directories(cls):
        """Ensure required directories exist."""
        os.makedirs(cls.CHECKPOINT_DIR, exist_ok=True)
        os.makedirs(cls.DATA_DIR, exist_ok=True)
