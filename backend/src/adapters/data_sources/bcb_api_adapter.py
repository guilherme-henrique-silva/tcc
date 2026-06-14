"""BcbApiAdapter — Selic e dólar via API do Banco Central do Brasil.

Períodos >= 1 ano são fracionados automaticamente em chamadas anuais para
respeitar a limitação da API. Os resultados parciais são concatenados e
deduplicados antes de retornar.
"""

from datetime import date, datetime
from typing import List, Optional

import httpx
import pandas as pd

from app.core.config import Config
from src.adapters.data_sources.bcb_dtos import (
    SelicRecordDTO,
    PtaxResponseDTO,
    DolarCotacaoDTO,
)
from src.domain.value_objects.date_range import DateRange


class BcbApiAdapter:
    """Recupera Selic e dólar da API do Banco Central."""

    _MAX_DAYS_PER_REQUEST = 365

    def __init__(self, config: Optional[Config] = None, timeout: float = 30.0):
        self.config = config or Config()
        self.timeout = timeout

    def fetch_selic(self, date_range: Optional[DateRange] = None) -> List[SelicRecordDTO]:
        """GET na série Selic, fracionando em janelas anuais quando necessário."""
        if date_range is None:
            payload = self._get_json(self.config.API_BCB_SELIC)
            return [SelicRecordDTO.model_validate(item) for item in payload]

        all_records: List[SelicRecordDTO] = []
        seen_dates: set = set()

        for chunk in date_range.split(self._MAX_DAYS_PER_REQUEST):
            url = self._build_selic_url(chunk)
            payload = self._get_json(url)
            for item in payload:
                record = SelicRecordDTO.model_validate(item)
                if record.data not in seen_dates:
                    seen_dates.add(record.data)
                    all_records.append(record)

        return all_records

    def fetch_dolar(self, date_range: Optional[DateRange] = None) -> PtaxResponseDTO:
        """GET na série PTAX, fracionando em janelas anuais quando necessário."""
        if date_range is None:
            payload = self._get_json(self.config.API_BCB_DOLAR)
            return PtaxResponseDTO.model_validate(payload)

        all_cotacoes: List[DolarCotacaoDTO] = []
        seen: set = set()

        for chunk in date_range.split(self._MAX_DAYS_PER_REQUEST):
            url = self._build_dolar_url(chunk)
            payload = self._get_json(url)
            response = PtaxResponseDTO.model_validate(payload)
            for cotacao in response.value:
                key = cotacao.data_hora_cotacao
                if key not in seen:
                    seen.add(key)
                    all_cotacoes.append(cotacao)

        return PtaxResponseDTO(value=all_cotacoes)

    def to_dataframe(self, date_range: Optional[DateRange] = None) -> pd.DataFrame:
        """Normaliza Selic e dólar em DataFrame (date/selic/usd_brl_compra/usd_brl_venda)."""
        selic_df = self._selic_to_dataframe(self.fetch_selic(date_range))
        dolar_df = self._dolar_to_dataframe(self.fetch_dolar(date_range))

        merged = selic_df.merge(dolar_df, on="date", how="outer")
        merged = merged.sort_values("date").reset_index(drop=True)
        return merged

    # ---------------------------------------------------------------------- #
    # URL builders                                                             #
    # ---------------------------------------------------------------------- #

    def _build_selic_url(self, chunk: DateRange) -> str:
        """Constrói a URL da Selic com as datas do chunk (DD/MM/YYYY)."""
        base = self.config.API_BCB_SELIC
        if not base:
            raise ValueError("API_BCB_SELIC não configurada")

        start = chunk.start_date.strftime("%d/%m/%Y")
        end = chunk.end_date.strftime("%d/%m/%Y")

        # Substitui os parâmetros de data se já estiverem na URL, ou acrescenta
        if "dataInicial=" in base or "dataFinal=" in base:
            import re
            base = re.sub(r"dataInicial=[^&]*", f"dataInicial={start}", base)
            base = re.sub(r"dataFinal=[^&]*", f"dataFinal={end}", base)
            return base

        sep = "&" if "?" in base else "?"
        return f"{base}{sep}dataInicial={start}&dataFinal={end}"

    def _build_dolar_url(self, chunk: DateRange) -> str:
        """Constrói a URL PTAX com as datas do chunk (MM-DD-YYYY)."""
        base = self.config.API_BCB_DOLAR
        if not base:
            raise ValueError("API_BCB_DOLAR não configurada")

        start = chunk.start_date.strftime("%m-%d-%Y")
        end = chunk.end_date.strftime("%m-%d-%Y")

        if "@dataInicial=" in base or "@dataFinal=" in base:
            import re
            base = re.sub(r"@dataInicial='[^']*'", f"@dataInicial='{start}'", base)
            base = re.sub(r"@dataFinal='[^']*'", f"@dataFinal='{end}'", base)
            return base

        sep = "&" if "?" in base else "?"
        return f"{base}{sep}@dataInicial='{start}'&@dataFinal='{end}'"

    # ---------------------------------------------------------------------- #
    # HTTP                                                                     #
    # ---------------------------------------------------------------------- #

    def _get_json(self, url: str):
        if not url:
            raise ValueError("URL do endpoint BCB não configurada")

        response = httpx.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    # ---------------------------------------------------------------------- #
    # Conversão para DataFrame                                                 #
    # ---------------------------------------------------------------------- #

    def _selic_to_dataframe(self, records: List[SelicRecordDTO]) -> pd.DataFrame:
        rows = [
            {
                "date": datetime.strptime(record.data, "%d/%m/%Y").date(),
                "selic": float(record.valor),
            }
            for record in records
        ]
        return pd.DataFrame(rows, columns=["date", "selic"])

    def _dolar_to_dataframe(self, response: PtaxResponseDTO) -> pd.DataFrame:
        rows = [
            {
                "date": self._parse_ptax_date(cotacao.data_hora_cotacao),
                "usd_brl_compra": cotacao.cotacao_compra,
                "usd_brl_venda": cotacao.cotacao_venda,
            }
            for cotacao in response.value
        ]
        return pd.DataFrame(rows, columns=["date", "usd_brl_compra", "usd_brl_venda"])

    def _parse_ptax_date(self, raw: str) -> date:
        return datetime.fromisoformat(raw).date()
