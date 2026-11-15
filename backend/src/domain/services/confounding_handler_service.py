"""Confounding Handler Service — variáveis de controle e dataset de análise por pregão.

Os controles entram **sempre** no modelo, sem filtro por p-valor (decisão do TCC):
Ibovespa, concorrentes, variação do USD/BRL, commodities agrícolas e indicador do Copom.
O teste de Granger propriamente dito vive em ``GrangerCausalityService``.
"""

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.domain.models import StockPrice
from src.domain.services.feature_engineering_service import log_returns_on_sessions
from src.domain.value_objects import DateRange
from src.adapters.data_sources.bcb_api_adapter import BcbApiAdapter

NEWS_COLUMNS = ["n_news", "n_pos", "n_neg", "n_neu", "sent_net", "has_news"]
TARGET_COLUMNS = [
    "log_return",
    "abs_return",
    "daily_return_pct",
    "volatility_20d",
    "volume_normalized",
    "anomaly_flag",
]


@dataclass(frozen=True)
class MacroeconomicIndicator:
    """Represents a macroeconomic indicator value."""

    indicator_name: str
    date: datetime
    value: float
    unit: str
    source: str
    metadata: Optional[Dict] = None


class ConfoundingHandlerService:
    """Builds the fixed control variables and assembles the analysis dataset."""

    def __init__(
        self,
        bcb_adapter: Optional[BcbApiAdapter] = None,
        copom_decision_dates: Optional[Sequence[object]] = None,
    ):
        """Initialize service with the Banco Central adapter and the Copom calendar."""
        self.bcb_adapter = bcb_adapter or BcbApiAdapter()
        self.copom_decision_dates = parse_dates(copom_decision_dates or [])

    # ------------------------------------------------------------------ #
    # Controles                                                           #
    # ------------------------------------------------------------------ #
    def usd_brl_control(self, sessions: Sequence[date]) -> pd.Series:
        """``d_usdbrl`` = ln(PTAX_t) − ln(PTAX_{t-1}) (PTAX de venda), por pregão.

        A PTAX é repetida (*forward-fill*) nos pregões sem cotação **antes** de tirar a
        diferença. A API devolve vários boletins por dia; vale o último (fechamento).
        """
        ordered = sorted(set(sessions))
        date_range = DateRange(ordered[0], ordered[-1])
        frame = self.bcb_adapter.dolar_dataframe(date_range)

        daily = (
            frame.dropna(subset=["usd_brl_venda"])
            .groupby("date")["usd_brl_venda"]
            .last()
            .astype(float)
        )

        if daily.empty:
            raise ValueError("A API do Banco Central não devolveu PTAX no período.")

        index = pd.Index(ordered, name="date")
        union = daily.index.union(index)
        on_sessions = daily.reindex(union).ffill().reindex(index).bfill()

        return np.log(on_sessions).diff().rename("d_usdbrl")

    def commodity_control(
        self,
        commodity_prices: Dict[str, Sequence[StockPrice]],
        sessions: Sequence[date],
    ) -> Optional[pd.Series]:
        """``ret_commod`` = média simples dos log-retornos dos futuros, nos pregões da B3.

        Preços são alinhados aos pregões com *forward-fill* (bolsa americana fechada).
        Devolve None quando não há nenhuma commodity.
        """
        returns = {
            ticker: log_returns_on_sessions(prices, sessions)
            for ticker, prices in commodity_prices.items()
            if prices
        }

        if not returns:
            return None

        return pd.DataFrame(returns).mean(axis=1).rename("ret_commod")

    def copom_indicator(self, sessions: Sequence[date]) -> pd.Series:
        """``copom`` = 1 no primeiro pregão **estritamente posterior** a cada decisão.

        O comunicado sai depois do fechamento da B3; por isso o dia do anúncio não conta.
        """
        ordered = sorted(set(sessions))
        flags = pd.Series(0, index=pd.Index(ordered, name="date"), dtype=int, name="copom")

        for decision in self.copom_decision_dates:
            position = bisect_right(ordered, decision)
            if position < len(ordered):
                flags.iloc[position] = 1

        return flags

    # ------------------------------------------------------------------ #
    # Dataset de análise                                                  #
    # ------------------------------------------------------------------ #
    def build_analysis_dataset(
        self,
        target_features: pd.DataFrame,
        news_features: pd.DataFrame,
        controls: Dict[str, pd.Series],
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Junta, por pregão, alvo + notícias + controles (contrato do §5 da spec).

        Descarta a primeira linha (retornos NaN). Devolve ``(dataset, avisos)``; uma
        linha por pregão menos uma, ordenada por ``date`` e sem NaN nas colunas
        obrigatórias.
        """
        warnings: List[str] = []
        frame = self._base_frame(target_features, news_features)

        for name, series in controls.items():
            frame[name] = frame["date"].map(series.to_dict()).astype(float)

        frame = frame.iloc[1:].reset_index(drop=True)
        required = ["log_return", *NEWS_COLUMNS, *controls.keys()]
        incomplete = int(frame[required].isna().any(axis=1).sum())

        if incomplete:
            warnings.append(
                f"{incomplete} pregão(ões) removido(s) do dataset por dados ausentes."
            )
            frame = frame.dropna(subset=required).reset_index(drop=True)

        return frame, warnings

    @staticmethod
    def _base_frame(target_features: pd.DataFrame, news_features: pd.DataFrame) -> pd.DataFrame:
        """Alvo à esquerda, notícias por pregão (zeros onde faltar linha)."""
        target_cols = ["date"] + [c for c in TARGET_COLUMNS if c in target_features.columns]
        frame = target_features[target_cols].copy().sort_values("date").reset_index(drop=True)

        news = news_features if not news_features.empty else pd.DataFrame(columns=["date"])
        frame = frame.merge(news, on="date", how="left")

        for column in NEWS_COLUMNS:
            if column not in frame.columns:
                frame[column] = 0

            frame[column] = frame[column].fillna(0)

        for column in ("n_news", "n_pos", "n_neg", "n_neu", "has_news"):
            frame[column] = frame[column].astype(int)

        return frame


def parse_dates(values: Sequence[object]) -> List[date]:
    """Converte datas ISO (ou ``date``) em ``date``; ValueError cita o valor inválido."""
    parsed: List[date] = []

    for value in values:
        if isinstance(value, datetime):
            parsed.append(value.date())
        elif isinstance(value, date):
            parsed.append(value)
        else:
            try:
                parsed.append(date.fromisoformat(str(value).strip()))
            except ValueError as exc:
                raise ValueError(
                    f"Data inválida em COPOM_DECISION_DATES: '{value}' (use YYYY-MM-DD)."
                ) from exc

    return sorted(set(parsed))
