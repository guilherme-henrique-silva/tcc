"""Feature Engineering Service — features de ações, notícias e concorrentes por pregão.

Todas as séries são indexadas pelos **pregões da B3** (``date``). O retorno logarítmico
``ln(Pt / Pt-1)`` sobre o fechamento ajustado é a variável dependente do teste de Granger;
volatilidade móvel e normalização de volume ficam apenas para visualização/exploração.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from src.domain.models import StockPrice, News
from src.domain.value_objects import TickerSymbol

PEERS_MEAN = "mean"
PEERS_SEPARATE = "separate"


@dataclass(frozen=True)
class StockFeatures:
    """Encapsulates calculated stock features."""

    ticker: TickerSymbol
    date: datetime
    log_return: float
    daily_return_pct: float
    volatility_20d: float
    volume_normalized: float
    anomaly_flag: bool


@dataclass(frozen=True)
class NewsFeatures:
    """Encapsulates calculated news features for one trading session."""

    date: date
    n_news: int
    sent_net: float
    has_news: int


# ---------------------------------------------------------------------- #
# Utilitários de retorno (única definição, usada por alvo, índice,        #
# concorrentes e commodities)                                             #
# ---------------------------------------------------------------------- #
def close_series(prices: Sequence[StockPrice]) -> pd.Series:
    """Fechamento ajustado indexado pela data civil (``date``), ordenado e sem duplicatas."""
    if not prices:
        return pd.Series(dtype=float)

    closes = {_as_date(p.date): float(p.close_price) for p in prices}
    series = pd.Series(closes, dtype=float).sort_index()
    series.index.name = "date"
    return series


def log_returns(prices: Sequence[StockPrice]) -> pd.Series:
    """Retorno logarítmico diário ``ln(Pt / Pt-1)`` (preço de fechamento ajustado).

    O primeiro valor é NaN (não há preço anterior). A série é indexada por ``date``.
    """
    closes = close_series(prices)
    if closes.empty:
        return closes

    return np.log(closes / closes.shift(1))


def log_returns_on_sessions(
    prices: Sequence[StockPrice],
    sessions: Sequence[date],
) -> pd.Series:
    """Log-retorno entre pregões consecutivos da B3, com preço repetido (*forward-fill*)
    nos pregões em que a bolsa da série não abriu.

    O preço é repetido **antes** de tirar a diferença; assim feriado estrangeiro vira
    retorno zero e o retorno do dia seguinte não é inflado.
    """
    index = pd.Index(sorted(set(sessions)), name="date")
    closes = close_series(prices)

    if closes.empty or index.empty:
        return pd.Series(np.nan, index=index, dtype=float)

    union = closes.index.union(index)
    on_sessions = closes.reindex(union).ffill().reindex(index).bfill()
    return np.log(on_sessions / on_sessions.shift(1))


class FeatureEngineeringService:
    """Service for calculating features from stock prices and news."""

    def __init__(self, volatility_window: int = 20, anomaly_std_threshold: float = 2.0):
        """Initialize with configuration parameters."""
        self.volatility_window = volatility_window
        self.anomaly_std_threshold = anomaly_std_threshold

    # ------------------------------------------------------------------ #
    # RF-05 — ações                                                       #
    # ------------------------------------------------------------------ #
    def calculate_stock_features(
        self,
        ticker: TickerSymbol,
        prices: List[StockPrice],
    ) -> pd.DataFrame:
        """Calculate stock features per trading session.

        Colunas: ``date``, ``log_return`` (Y do teste), ``abs_return`` (robustez),
        ``daily_return_pct``, ``volatility_20d`` (só visualização),
        ``volume_normalized`` (sem *look-ahead*) e ``anomaly_flag`` (descritiva).
        """
        if not prices:
            return pd.DataFrame()

        prices_df = self._convert_prices_to_dataframe(self._sort_prices_by_date(prices))
        log_ret = np.log(prices_df["close"] / prices_df["close"].shift(1))

        features_df = pd.DataFrame()
        features_df["date"] = prices_df["date"]
        features_df["log_return"] = log_ret
        features_df["abs_return"] = log_ret.abs()
        features_df["daily_return_pct"] = prices_df["close"].pct_change() * 100
        features_df["volatility_20d"] = log_ret.rolling(window=self.volatility_window).std()
        features_df["volume_normalized"] = self._normalize_volume(prices_df)
        features_df["anomaly_flag"] = self._detect_anomalies(log_ret)

        return features_df

    def _normalize_volume(self, prices_df: pd.DataFrame) -> pd.Series:
        """Volume em [0, 1] com mínimo/máximo **expansivos** (só dados até t, sem look-ahead).

        Vale 0,5 quando máximo e mínimo acumulados coincidem.
        """
        volume = prices_df["volume"].astype(float)
        running_min = volume.expanding().min()
        running_max = volume.expanding().max()
        spread = running_max - running_min

        normalized = (volume - running_min) / spread.where(spread != 0)
        return normalized.where(spread != 0, 0.5)

    def _detect_anomalies(self, log_ret: pd.Series) -> pd.Series:
        """Anomalia descritiva: ``|r - mu| > k * sigma`` (k = ANOMALY_STD_THRESHOLD)."""
        mean_return = log_ret.mean()
        std_dev = log_ret.std()

        if pd.isna(std_dev) or std_dev == 0:
            return pd.Series(False, index=log_ret.index)

        return (log_ret - mean_return).abs() > self.anomaly_std_threshold * std_dev

    # ------------------------------------------------------------------ #
    # RF-06 — notícias por pregão                                         #
    # ------------------------------------------------------------------ #
    def calculate_news_features(
        self,
        news_by_session: Dict[date, List[News]],
        sessions: Sequence[date],
    ) -> pd.DataFrame:
        """Uma linha por pregão (inclusive os sem notícia).

        ``n_news`` (Nt), ``n_pos``/``n_neg``/``n_neu`` (contagens por score +1/−1/0),
        ``sent_net`` (St = (n_pos − n_neg) / n_news; 0 quando n_news = 0) e
        ``has_news`` (Dt). Notícia sem ``sentiment_score`` conta em ``n_news``, mas não
        em ``n_pos``/``n_neg``/``n_neu``.
        """
        rows = [self._session_news_row(day, news_by_session.get(day, [])) for day in sessions]
        columns = ["date", "n_news", "n_pos", "n_neg", "n_neu", "sent_net", "has_news"]

        return pd.DataFrame(rows, columns=columns)

    def _session_news_row(self, day: date, items: List[News]) -> Dict[str, object]:
        """Contagens e sentimento líquido de um pregão."""
        scores = [item.sentiment_score.value for item in items if item.sentiment_score]
        n_pos = sum(1 for s in scores if s > 0)
        n_neg = sum(1 for s in scores if s < 0)
        n_neu = sum(1 for s in scores if s == 0)
        n_news = len(items)

        return {
            "date": day,
            "n_news": n_news,
            "n_pos": n_pos,
            "n_neg": n_neg,
            "n_neu": n_neu,
            "sent_net": (n_pos - n_neg) / n_news if n_news else 0.0,
            "has_news": 1 if n_news else 0,
        }

    @staticmethod
    def count_unscored(news_by_session: Dict[date, List[News]]) -> int:
        """Notícias alinhadas que ficaram sem ``sentiment_score``."""
        return sum(
            1
            for items in news_by_session.values()
            for item in items
            if item.sentiment_score is None
        )

    # ------------------------------------------------------------------ #
    # RF-07 — concorrentes                                                #
    # ------------------------------------------------------------------ #
    def calculate_peer_returns(
        self,
        prices_dict: Dict[str, List[StockPrice]],
        target_ticker: str,
        sessions: Sequence[date],
        aggregation: str = PEERS_MEAN,
    ) -> pd.DataFrame:
        """Controle de concorrentes por pregão (o alvo fica de fora).

        ``mean``: coluna ``ret_peers`` = média simples dos log-retornos.
        ``separate``: uma coluna por concorrente (``ret_itub4`` etc.).
        Concorrentes sem cotação são ignorados; sem nenhum, devolve DataFrame vazio.
        """
        returns = {
            ticker: log_returns_on_sessions(prices, sessions)
            for ticker, prices in prices_dict.items()
            if ticker != target_ticker and prices
        }

        if not returns:
            return pd.DataFrame()

        if aggregation == PEERS_SEPARATE:
            frame = pd.DataFrame({peer_column(t): s for t, s in returns.items()})
        else:
            frame = pd.DataFrame({"ret_peers": pd.DataFrame(returns).mean(axis=1)})

        frame.index.name = "date"
        return frame.reset_index()

    def calculate_competitor_features(
        self,
        tickers: List[TickerSymbol],
        prices_dict: Dict[str, List[StockPrice]],
        target_ticker: str = "BBAS3.SA",
    ) -> pd.DataFrame:
        """Co-movimento descritivo com o alvo (correlação de Pearson e ``sync_score``).

        Calculado sobre log-retornos **alinhados por data** e só para os concorrentes
        (o alvo é excluído), na mesma ordem das correlações.
        """
        target_returns = log_returns(prices_dict.get(target_ticker, []))
        peers = [str(t) for t in tickers if str(t) != target_ticker]

        correlations = [
            self._aligned_correlation(target_returns, log_returns(prices_dict.get(p, [])))
            for p in peers
        ]
        sync_scores = [self._sync_score(c) for c in correlations]

        return pd.DataFrame({
            "ticker": peers,
            "correlation_with_bbas3": correlations,
            "sync_score": sync_scores,
        })

    @staticmethod
    def _aligned_correlation(first: pd.Series, second: pd.Series) -> float:
        """Pearson entre duas séries alinhadas pelo índice (data); 0.0 sem dados."""
        if first.empty or second.empty:
            return 0.0

        joined = pd.concat([first, second], axis=1, join="inner").dropna()
        if len(joined) < 2:
            return 0.0

        corr = joined.iloc[:, 0].corr(joined.iloc[:, 1])
        return 0.0 if pd.isna(corr) else float(corr)

    @staticmethod
    def _sync_score(correlation: float) -> float:
        """Correlação mapeada para [0, 1]."""
        return (correlation + 1.0) / 2.0

    # ------------------------------------------------------------------ #
    # Auxiliares                                                          #
    # ------------------------------------------------------------------ #
    def _sort_prices_by_date(self, prices: List[StockPrice]) -> List[StockPrice]:
        """Sort prices chronologically."""
        return sorted(prices, key=lambda p: p.date)

    def _convert_prices_to_dataframe(self, prices: List[StockPrice]) -> pd.DataFrame:
        """Convert StockPrice list to DataFrame (``date`` civil) for calculations."""
        return pd.DataFrame({
            "date": [_as_date(p.date) for p in prices],
            "close": [p.close_price for p in prices],
            "volume": [p.volume for p in prices],
            "high": [p.high_price for p in prices],
            "low": [p.low_price for p in prices],
        })


def peer_column(ticker: str) -> str:
    """Nome da coluna de um concorrente em modo ``separate`` (ITUB4.SA -> ret_itub4)."""
    return f"ret_{ticker.split('.')[0].lower()}"


def _as_date(value: object) -> date:
    """``datetime`` (com ou sem fuso) -> ``date`` civil local; ``date`` passa direto."""
    if isinstance(value, datetime):
        return value.date()

    return value
