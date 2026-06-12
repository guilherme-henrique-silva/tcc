"""Feature Engineering Service - Tópico 2.4."""

from dataclasses import dataclass
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.domain.value_objects import TickerSymbol, DateRange
from src.domain.models import StockPrice, News, FeatureSet


@dataclass(frozen=True)
class StockFeatures:
    """Encapsulates calculated stock features (Rule 4: First Class Collection)."""
    
    ticker: TickerSymbol
    date: datetime
    daily_return_pct: float
    volatility_20d: float
    volume_normalized: float
    anomaly_flag: bool


@dataclass(frozen=True)
class NewsFeatures:
    """Encapsulates calculated news features (Rule 4)."""
    
    date: datetime
    sentiment_score: float
    news_frequency: int
    tfidf_components: np.ndarray
    entities: List[str]


class FeatureEngineeringService:
    """Service for calculating features from stock prices and news (Rule 7: small entities)."""
    
    def __init__(self, volatility_window: int = 20, anomaly_std_threshold: float = 2.0):
        """Initialize with configuration parameters."""
        self.volatility_window = volatility_window
        self.anomaly_std_threshold = anomaly_std_threshold
    
    def calculate_stock_features(
        self,
        ticker: TickerSymbol,
        prices: List[StockPrice],
    ) -> pd.DataFrame:
        """
        Calculate stock features from price data.
        
        Returns DataFrame with daily_return_pct, volatility_20d, volume_normalized, anomaly_flag.
        """
        if not prices:
            return pd.DataFrame()
        
        prices_sorted = self._sort_prices_by_date(prices)
        prices_df = self._convert_prices_to_dataframe(prices_sorted)
        
        features_df = pd.DataFrame()
        features_df["date"] = prices_df["date"]
        features_df["daily_return_pct"] = self._calculate_returns(prices_df)
        features_df["volatility_20d"] = self._calculate_volatility(prices_df)
        features_df["volume_normalized"] = self._normalize_volume(prices_df)
        features_df["anomaly_flag"] = self._detect_anomalies(features_df)
        
        return features_df
    
    def calculate_news_features(
        self,
        news_items: List[News],
        date_range: DateRange,
    ) -> pd.DataFrame:
        """Calculate news features within date range."""
        filtered_news = self._filter_news_by_date_range(news_items, date_range)
        
        if not filtered_news:
            return pd.DataFrame()
        
        news_df = pd.DataFrame()
        news_df["date"] = [item.created_at.date() for item in filtered_news]
        news_df["sentiment_score"] = self._aggregate_sentiment(filtered_news)
        news_df["news_frequency"] = self._count_news_frequency(filtered_news)
        
        return news_df
    
    def calculate_competitor_features(
        self,
        tickers: List[TickerSymbol],
        prices_dict: Dict[str, List[StockPrice]],
    ) -> pd.DataFrame:
        """Calculate competitor co-movement features."""
        correlations = self._compute_correlations(prices_dict)
        sync_scores = self._compute_synchronization(prices_dict)
        
        features_df = pd.DataFrame({
            "ticker": [str(t) for t in tickers],
            "correlation_with_bbas3": correlations,
            "sync_score": sync_scores,
        })
        
        return features_df
    
    def _sort_prices_by_date(self, prices: List[StockPrice]) -> List[StockPrice]:
        """Sort prices chronologically (Rule 1: delegate to helper)."""
        return sorted(prices, key=lambda p: p.date)
    
    def _convert_prices_to_dataframe(self, prices: List[StockPrice]) -> pd.DataFrame:
        """Convert StockPrice list to DataFrame for calculations (Rule 1)."""
        return pd.DataFrame({
            "date": [p.date for p in prices],
            "close": [p.close_price for p in prices],
            "volume": [p.volume for p in prices],
            "high": [p.high_price for p in prices],
            "low": [p.low_price for p in prices],
        })
    
    def _calculate_returns(self, prices_df: pd.DataFrame) -> pd.Series:
        """Calculate daily percentage returns (Rule 1)."""
        return prices_df["close"].pct_change() * 100
    
    def _calculate_volatility(self, prices_df: pd.DataFrame) -> pd.Series:
        """Calculate rolling volatility over window (Rule 1)."""
        returns = self._calculate_returns(prices_df)
        return returns.rolling(window=self.volatility_window).std()
    
    def _normalize_volume(self, prices_df: pd.DataFrame) -> pd.Series:
        """Normalize volume to 0-1 scale (Rule 1)."""
        volume_min = prices_df["volume"].min()
        volume_max = prices_df["volume"].max()
        
        if volume_max == volume_min:
            return pd.Series(0.5, index=prices_df.index)
        
        return (prices_df["volume"] - volume_min) / (volume_max - volume_min)
    
    def _detect_anomalies(self, features_df: pd.DataFrame) -> pd.Series:
        """Detect anomalies using standard deviation threshold (Rule 1)."""
        returns = features_df["daily_return_pct"]
        std_dev = returns.std()
        mean_return = returns.mean()
        
        threshold = self.anomaly_std_threshold * std_dev
        is_anomaly = returns.abs() - mean_return.abs() > threshold
        
        return is_anomaly
    
    def _filter_news_by_date_range(
        self,
        news_items: List[News],
        date_range: DateRange,
    ) -> List[News]:
        """Filter news items within date range (Rule 2: no else, early return)."""
        if not news_items:
            return []
        
        return [
            item for item in news_items
            if date_range.contains(item.created_at.date())
        ]
    
    def _aggregate_sentiment(self, news_items: List[News]) -> List[float]:
        """Aggregate sentiment scores by day (Rule 1)."""
        if not news_items:
            return []
        
        sentiment_by_date = self._group_sentiment_by_date(news_items)
        return [
            self._calculate_daily_sentiment_average(scores)
            for scores in sentiment_by_date.values()
        ]
    
    def _group_sentiment_by_date(
        self,
        news_items: List[News],
    ) -> Dict[str, List[float]]:
        """Group sentiment scores by date (Rule 1)."""
        grouped = {}
        
        for item in news_items:
            date_key = str(item.created_at.date())
            
            if date_key not in grouped:
                grouped[date_key] = []
            
            sentiment_value = item.sentiment_score.value if item.sentiment_score else 0
            grouped[date_key].append(float(sentiment_value))
        
        return grouped
    
    def _calculate_daily_sentiment_average(self, scores: List[float]) -> float:
        """Calculate average sentiment for day (Rule 1)."""
        if not scores:
            return 0.0
        
        return sum(scores) / len(scores)
    
    def _count_news_frequency(self, news_items: List[News]) -> List[int]:
        """Count news frequency by day (Rule 1)."""
        frequency_by_date = self._group_news_by_date(news_items)
        return list(frequency_by_date.values())
    
    def _group_news_by_date(self, news_items: List[News]) -> Dict[str, int]:
        """Group and count news by date (Rule 1)."""
        grouped = {}
        
        for item in news_items:
            date_key = str(item.created_at.date())
            grouped[date_key] = grouped.get(date_key, 0) + 1
        
        return grouped
    
    def _compute_correlations(
        self,
        prices_dict: Dict[str, List[StockPrice]],
    ) -> List[float]:
        """Compute correlation with BBAS3 (Rule 1)."""
        correlations = []
        
        for ticker, prices in prices_dict.items():
            if ticker == "BBAS3.SA":
                continue
            
            corr_value = self._calculate_ticker_correlation(
                prices_dict.get("BBAS3.SA", []),
                prices
            )
            correlations.append(corr_value)
        
        return correlations
    
    def _calculate_ticker_correlation(
        self,
        bbas3_prices: List[StockPrice],
        ticker_prices: List[StockPrice],
    ) -> float:
        """Calculate correlation between two price series (Rule 1)."""
        if not bbas3_prices or not ticker_prices:
            return 0.0
        
        bbas3_df = self._convert_prices_to_dataframe(bbas3_prices)
        ticker_df = self._convert_prices_to_dataframe(ticker_prices)
        
        returns_bbas3 = bbas3_df["close"].pct_change()
        returns_ticker = ticker_df["close"].pct_change()
        
        return float(returns_bbas3.corr(returns_ticker))
    
    def _compute_synchronization(
        self,
        prices_dict: Dict[str, List[StockPrice]],
    ) -> List[float]:
        """Compute synchronization score (Rule 1)."""
        sync_scores = []
        
        for ticker in prices_dict.keys():
            if ticker == "BBAS3.SA":
                continue
            
            score = self._calculate_sync_score(prices_dict, ticker)
            sync_scores.append(score)
        
        return sync_scores
    
    def _calculate_sync_score(
        self,
        prices_dict: Dict[str, List[StockPrice]],
        ticker: str,
    ) -> float:
        """Calculate synchronization between ticker and BBAS3 (Rule 1)."""
        if ticker not in prices_dict:
            return 0.0
        
        corr = self._calculate_ticker_correlation(
            prices_dict.get("BBAS3.SA", []),
            prices_dict[ticker]
        )
        
        # Sync score is correlation mapped to 0-1 range
        return (corr + 1.0) / 2.0
