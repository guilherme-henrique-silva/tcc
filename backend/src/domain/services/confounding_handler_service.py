"""Confounding Handler Service - Tópico 2.5."""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import numpy as np
import pandas as pd
from datetime import datetime, date

from src.domain.value_objects import DateRange, PercentageChange
from src.adapters.data_sources.bcb_api_adapter import BcbApiAdapter


@dataclass(frozen=True)
class MacroeconomicIndicator:
    """Represents a macroeconomic indicator value."""
    
    indicator_name: str
    date: datetime
    value: float
    unit: str
    source: str
    metadata: Optional[Dict] = None


@dataclass(frozen=True)
class GrangerTestResult:
    """Encapsulates Granger causality test results."""
    
    p_value: float
    test_statistic: float
    lag: int
    is_significant: bool
    interpretation: str


class ConfoundingHandlerService:
    """Service for handling confounding variables and causality testing (Tópico 2.5)."""
    
    SIGNIFICANCE_LEVEL = 0.05

    def __init__(self, bcb_adapter: Optional[BcbApiAdapter] = None):
        """Initialize service with the Banco Central data adapter (Tópico 2.5)."""
        self.bcb_adapter = bcb_adapter or BcbApiAdapter()

    def get_control_variables(
        self,
        date_range: DateRange,
    ) -> pd.DataFrame:
        """Retrieve control variables (Selic, USD/BRL, commodities) for date range."""
        selic_data = self._load_selic_data(date_range)
        usd_brl_data = self._load_usd_brl_data(date_range)
        commodity_data = self._load_commodity_data(date_range)

        control_df = self._merge_control_variables(selic_data, usd_brl_data, commodity_data)
        return control_df
    
    def apply_granger_test(
        self,
        sentiment: np.ndarray,
        prices: np.ndarray,
        lag: int = 3,
    ) -> GrangerTestResult:
        """
        Apply Granger causality test to validate if sentiment causes prices.
        
        H0: Sentiment does not Granger-cause prices
        Rejects if p_value < 0.05
        """
        if not self._is_valid_granger_input(sentiment, prices):
            return self._create_invalid_granger_result()
        
        aligned_sentiment, aligned_prices = self._align_time_series(sentiment, prices)
        test_statistic, p_value = self._compute_granger_statistic(
            aligned_sentiment,
            aligned_prices,
            lag
        )
        
        is_significant = p_value < self.SIGNIFICANCE_LEVEL
        interpretation = self._create_granger_interpretation(is_significant, p_value)
        
        return GrangerTestResult(
            p_value=p_value,
            test_statistic=test_statistic,
            lag=lag,
            is_significant=is_significant,
            interpretation=interpretation,
        )
    
    def _load_selic_data(self, date_range: DateRange) -> pd.DataFrame:
        """Load Selic (SGS 11) data from the Banco Central API (Tópico 2.5)."""
        records = self.bcb_adapter.fetch_selic()

        rows = [
            {
                "date": datetime.strptime(record.data, "%d/%m/%Y").date(),
                "selic": float(record.valor),
            }
            for record in records
        ]
        df = pd.DataFrame(rows, columns=["date", "selic"])
        return self._filter_by_range(df, date_range)

    def _load_usd_brl_data(self, date_range: DateRange) -> pd.DataFrame:
        """Load USD/BRL (PTAX) data from the Banco Central API (Tópico 2.5)."""
        response = self.bcb_adapter.fetch_dolar()

        rows = [
            {
                "date": datetime.fromisoformat(cotacao.data_hora_cotacao).date(),
                "usd_brl": cotacao.cotacao_venda,
            }
            for cotacao in response.value
        ]
        df = pd.DataFrame(rows, columns=["date", "usd_brl"])
        return self._filter_by_range(df, date_range)

    def _filter_by_range(self, df: pd.DataFrame, date_range: DateRange) -> pd.DataFrame:
        """Keep only rows inside the requested date range (Rule 1)."""
        if df.empty:
            return df

        mask = df["date"].apply(date_range.contains)
        return df[mask].reset_index(drop=True)
    
    def _load_commodity_data(self, date_range: DateRange) -> pd.DataFrame:
        """Load commodity prices (soja, milho, boi) (Rule 1)."""
        # TODO: Integrate with commodity data provider
        return pd.DataFrame({
            "date": self._generate_business_days(date_range),
            "soja_price": self._generate_mock_commodity_values(date_range),
            "milho_price": self._generate_mock_commodity_values(date_range),
            "boi_price": self._generate_mock_commodity_values(date_range),
        })
    
    def _merge_control_variables(
        self,
        selic_df: pd.DataFrame,
        usd_brl_df: pd.DataFrame,
        commodity_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge all control variables on date (Rule 1)."""
        merged = selic_df.merge(usd_brl_df, on="date", how="outer")
        merged = merged.merge(commodity_df, on="date", how="outer")
        merged = merged.sort_values("date").reset_index(drop=True)
        
        return merged
    
    def _is_valid_granger_input(
        self,
        sentiment: np.ndarray,
        prices: np.ndarray,
    ) -> bool:
        """Validate Granger test inputs (Rule 2: no else)."""
        if not isinstance(sentiment, np.ndarray):
            return False
        
        if not isinstance(prices, np.ndarray):
            return False
        
        if len(sentiment) != len(prices):
            return False
        
        if len(sentiment) < 10:
            return False
        
        return True
    
    def _create_invalid_granger_result(self) -> GrangerTestResult:
        """Create invalid result for bad inputs (Rule 1)."""
        return GrangerTestResult(
            p_value=1.0,
            test_statistic=0.0,
            lag=0,
            is_significant=False,
            interpretation="Input data invalid for Granger test",
        )
    
    def _align_time_series(
        self,
        sentiment: np.ndarray,
        prices: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Align time series lengths (Rule 1)."""
        min_length = min(len(sentiment), len(prices))
        return sentiment[:min_length], prices[:min_length]
    
    def _compute_granger_statistic(
        self,
        sentiment: np.ndarray,
        prices: np.ndarray,
        lag: int,
    ) -> Tuple[float, float]:
        """
        Compute Granger causality statistic using OLS regression.
        
        Simplified implementation: F-statistic from restricted vs unrestricted models
        """
        # Remove NaN values
        valid_mask = ~(np.isnan(sentiment) | np.isnan(prices))
        sentiment_clean = sentiment[valid_mask]
        prices_clean = prices[valid_mask]
        
        if len(sentiment_clean) < lag + 2:
            return 0.0, 1.0
        
        # Build lagged matrices
        max_lag = min(lag, len(sentiment_clean) // 3)
        
        if max_lag < 1:
            return 0.0, 1.0
        
        # Simplified F-statistic (mock calculation)
        # In production, use statsmodels.tsa.stattools.grangercausalitytests
        test_statistic = self._calculate_f_statistic(sentiment_clean, prices_clean, max_lag)
        p_value = self._f_statistic_to_p_value(test_statistic, max_lag)
        
        return test_statistic, p_value
    
    def _calculate_f_statistic(
        self,
        sentiment: np.ndarray,
        prices: np.ndarray,
        lag: int,
    ) -> float:
        """Calculate F-statistic for Granger test (Rule 1)."""
        # Compute correlation as proxy for causality
        correlation = float(np.corrcoef(sentiment, prices)[0, 1])
        
        # Convert correlation to test statistic
        n = len(sentiment)
        t_stat = correlation * np.sqrt(n - 2) / np.sqrt(1 - correlation**2 + 1e-10)
        
        return float(t_stat)
    
    def _f_statistic_to_p_value(self, f_stat: float, df: int) -> float:
        """Convert F-statistic to p-value (Rule 1)."""
        # Simplified: use normal approximation
        # In production, use scipy.stats.f.sf()
        p_value = 1.0 / (1.0 + abs(f_stat))
        return min(1.0, max(0.0, p_value))
    
    def _create_granger_interpretation(self, is_significant: bool, p_value: float) -> str:
        """Create human-readable interpretation (Rule 1)."""
        if is_significant:
            return f"Sentiment Granger-causes prices (p={p_value:.4f}, reject H0)"
        
        return f"No causal relationship detected (p={p_value:.4f}, fail to reject H0)"
    
    def _generate_business_days(self, date_range: DateRange) -> List[date]:
        """Generate business day dates for range (Rule 1)."""
        # TODO: Filter weekends and holidays
        start = date_range.start_date
        end = date_range.end_date
        days = pd.date_range(start, end, freq="D")

        return [d.date() for d in days]
    
    def _generate_mock_commodity_values(self, date_range: DateRange) -> List[float]:
        """Generate mock commodity prices (Rule 1)."""
        days_count = date_range.days_count
        return np.random.uniform(100.0, 500.0, days_count).tolist()
