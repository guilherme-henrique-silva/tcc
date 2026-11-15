"""Feature Engineering Stage."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.services.feature_engineering_service import (
    FeatureEngineeringService,
    log_returns_on_sessions,
)
from src.domain.services.session_alignment import (
    align_news_with_audit,
    parse_close_time,
    session_calendar,
)
from src.domain.value_objects import TickerSymbol
from app.core.config import Config
from app.core.logger import get_logger

logger = get_logger(__name__)


class FeatureEngineeringStage(PipelineStage):
    """Stage for calculating per-session features from stock and news data.

    Pipeline interna: calendário de pregões (datas com cotação do alvo) -> alinhamento das
    notícias ao pregão -> features de ações -> features de notícias -> concorrentes.
    """

    def __init__(
        self,
        *,
        target_ticker: Optional[str] = None,
        market_close_time: Optional[str] = None,
        peers_aggregation: Optional[str] = None,
        volatility_window: Optional[int] = None,
        anomaly_std_threshold: Optional[float] = None,
    ):
        """Initialize feature engineering service; defaults come from ``Config``."""
        super().__init__("feature_engineering")
        self.target_ticker = target_ticker or Config.TARGET_TICKER
        self.close_time = parse_close_time(market_close_time or Config.MARKET_CLOSE_TIME)
        self.peers_aggregation = peers_aggregation or Config.PEERS_AGGREGATION
        self.service = FeatureEngineeringService(
            volatility_window=volatility_window or Config.VOLATILITY_WINDOW,
            anomaly_std_threshold=anomaly_std_threshold or Config.ANOMALY_STD_THRESHOLD,
        )

    def substages(self) -> List[str]:
        """Subetapas em ordem."""
        return [
            "calendario_pregoes",
            "alinhar_noticias",
            "features_acoes",
            "features_noticias",
            "features_concorrentes",
        ]

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Calculate features."""
        start_time = datetime.now()

        try:
            stock_prices = self._extract_stock_prices(input_data)
            target_prices = stock_prices.get(self.target_ticker)

            if not target_prices:
                return self._create_failure_result(
                    start_time,
                    datetime.now(),
                    f"No stock prices available for target {self.target_ticker}",
                )

            self._report_substage(on_substage, "calendario_pregoes")
            sessions = session_calendar(target_prices)

            self._report_substage(on_substage, "alinhar_noticias")
            news_by_session, audit = align_news_with_audit(
                self._extract_news_items(input_data), sessions, self.close_time
            )
            audit["without_sentiment"] = self.service.count_unscored(news_by_session)
            self._log_audit(audit)

            self._report_substage(on_substage, "features_acoes")
            stock_features = self._calculate_stock_features(stock_prices)
            index_returns = self._calculate_index_returns(input_data, sessions)

            self._report_substage(on_substage, "features_noticias")
            news_features = self.service.calculate_news_features(news_by_session, sessions)

            self._report_substage(on_substage, "features_concorrentes")
            competitor_features = self._calculate_competitor_features(stock_prices)
            peer_returns = self.service.calculate_peer_returns(
                stock_prices, self.target_ticker, sessions, self.peers_aggregation
            )

            output_data = self._create_output_data(
                sessions,
                stock_features,
                news_features,
                competitor_features,
                peer_returns,
                index_returns,
                audit,
            )

            return self._create_success_result(
                start_time,
                datetime.now(),
                output_data,
            )

        except Exception as e:
            return self._create_failure_result(
                start_time,
                datetime.now(),
                str(e),
            )

    def validate(self) -> bool:
        """Validate service availability."""
        return self.service is not None

    def _extract_stock_prices(self, input_data: Dict[str, Any]) -> Dict[str, list]:
        """Extract stock prices from input."""
        return input_data.get("stock_prices", {})

    def _extract_news_items(self, input_data: Dict[str, Any]) -> list:
        """Extract news items from input."""
        return input_data.get("news_items", [])

    def _calculate_stock_features(self, stock_prices: Dict[str, list]) -> Dict[str, List[dict]]:
        """Calculate stock features (records) for the target and every competitor."""
        features_by_ticker: Dict[str, List[dict]] = {}

        for ticker_str, prices in stock_prices.items():
            if not prices:
                continue

            features_df = self.service.calculate_stock_features(TickerSymbol(ticker_str), prices)
            features_by_ticker[ticker_str] = _records(features_df)

        return features_by_ticker

    def _calculate_index_returns(
        self,
        input_data: Dict[str, Any],
        sessions: List[date],
    ) -> pd.DataFrame:
        """``ret_ibov``: log-retorno do índice de mercado nos pregões do alvo."""
        index_prices = input_data.get("index_prices") or []
        if not index_prices:
            return pd.DataFrame(columns=["date", "ret_ibov"])

        series = log_returns_on_sessions(index_prices, sessions).rename("ret_ibov")
        return series.reset_index()

    def _calculate_competitor_features(self, stock_prices: Dict[str, list]) -> List[dict]:
        """Descriptive co-movement of each competitor with the target."""
        tickers = [TickerSymbol(t) for t in stock_prices if stock_prices[t]]
        features_df = self.service.calculate_competitor_features(
            tickers, stock_prices, self.target_ticker
        )
        return _records(features_df)

    def _log_audit(self, audit: Dict[str, int]) -> None:
        """Surface alignment counters (and the discards) in the log."""
        logger.info("Alinhamento de notícias aos pregões: %s", audit)

        if audit["discarded_after_last_session"]:
            logger.warning(
                "%d notícia(s) descartada(s): publicadas depois do último pregão do período",
                audit["discarded_after_last_session"],
            )

    def _create_output_data(
        self,
        sessions: List[date],
        stock_features: Dict[str, List[dict]],
        news_features: pd.DataFrame,
        competitor_features: List[dict],
        peer_returns: pd.DataFrame,
        index_returns: pd.DataFrame,
        alignment_audit: Dict[str, int],
    ) -> Dict[str, Any]:
        """Create output data for next stage."""
        return {
            "sessions": sessions,
            "target_ticker": self.target_ticker,
            "stock_features": stock_features,
            "news_features": _records(news_features),
            "competitor_features": competitor_features,
            "peer_returns": _records(peer_returns),
            "index_returns": _records(index_returns),
            "alignment_audit": alignment_audit,
            "feature_timestamp": datetime.now().isoformat(),
        }


def _records(frame: pd.DataFrame) -> List[dict]:
    """DataFrame -> lista de dicts (vazia quando não há linhas)."""
    if frame is None or frame.empty:
        return []

    return frame.to_dict(orient="records")
