"""Data sources adapters."""

from .yfinance_adapter import YFinanceAdapter
from .csv_news_adapter import CsvNewsAdapter
from .bcb_api_adapter import BcbApiAdapter
from .bcb_dtos import SelicRecordDTO, DolarCotacaoDTO, PtaxResponseDTO

__all__ = [
    "YFinanceAdapter",
    "CsvNewsAdapter",
    "BcbApiAdapter",
    "SelicRecordDTO",
    "DolarCotacaoDTO",
    "PtaxResponseDTO",
]
