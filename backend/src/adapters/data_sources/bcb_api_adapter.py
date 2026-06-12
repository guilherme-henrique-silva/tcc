"""BcbApiAdapter - Selic e dólar via API do Banco Central (Tópico 2.5 / Seção 6)."""

from datetime import datetime
from typing import List, Optional

import httpx
import pandas as pd

from app.core.config import Config
from src.adapters.data_sources.bcb_dtos import (
    SelicRecordDTO,
    PtaxResponseDTO,
)


class BcbApiAdapter:
    """Recupera Selic e dólar da API do Banco Central (Tópico 2.5)."""

    def __init__(self, config: Optional[Config] = None, timeout: float = 30.0):
        """Initialize with configuration holding the parametrized endpoints."""
        self.config = config or Config()
        self.timeout = timeout

    def fetch_selic(self) -> List[SelicRecordDTO]:
        """GET em Config.API_BCB_SELIC; valida o array com SelicRecordDTO."""
        payload = self._get_json(self.config.API_BCB_SELIC)
        return [SelicRecordDTO.model_validate(item) for item in payload]

    def fetch_dolar(self) -> PtaxResponseDTO:
        """GET em Config.API_BCB_DOLAR; valida o envelope com PtaxResponseDTO."""
        payload = self._get_json(self.config.API_BCB_DOLAR)
        return PtaxResponseDTO.model_validate(payload)

    def to_dataframe(self) -> pd.DataFrame:
        """Normaliza Selic e dólar em DataFrame (date/selic/usd_brl_compra/usd_brl_venda)."""
        selic_df = self._selic_to_dataframe(self.fetch_selic())
        dolar_df = self._dolar_to_dataframe(self.fetch_dolar())

        merged = selic_df.merge(dolar_df, on="date", how="outer")
        merged = merged.sort_values("date").reset_index(drop=True)
        return merged

    def _get_json(self, url: str):
        """Perform a GET request and return parsed JSON (Rule 1)."""
        if not url:
            raise ValueError("BCB endpoint URL is not configured")

        response = httpx.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _selic_to_dataframe(self, records: List[SelicRecordDTO]) -> pd.DataFrame:
        """Convert Selic DTOs into a date/selic DataFrame (Rule 1)."""
        rows = [
            {
                "date": datetime.strptime(record.data, "%d/%m/%Y").date(),
                "selic": float(record.valor),
            }
            for record in records
        ]
        return pd.DataFrame(rows, columns=["date", "selic"])

    def _dolar_to_dataframe(self, response: PtaxResponseDTO) -> pd.DataFrame:
        """Convert PTAX DTOs into a date/usd DataFrame, dropping intraday time (Rule 1)."""
        rows = [
            {
                "date": self._parse_ptax_date(cotacao.data_hora_cotacao),
                "usd_brl_compra": cotacao.cotacao_compra,
                "usd_brl_venda": cotacao.cotacao_venda,
            }
            for cotacao in response.value
        ]
        columns = ["date", "usd_brl_compra", "usd_brl_venda"]
        return pd.DataFrame(rows, columns=columns)

    def _parse_ptax_date(self, raw: str):
        """Parse 'YYYY-MM-DD HH:MM:SS.fff' keeping only the day (Rule 1)."""
        return datetime.fromisoformat(raw).date()
