"""FeatureSet - First Class Collection for features (Regra 4)."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import pandas as pd
import numpy as np


@dataclass
class FeatureSet:
    """
    Base class for feature collections.
    
    Encapsulates feature data and provides methods for manipulation.
    Rule 4 (First Class Collections): Collections have their own behavior.
    """
    
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    metadata: Dict = field(default_factory=dict)
    
    @property
    def shape(self) -> tuple:
        """Return data shape."""
        return self.data.shape
    
    @property
    def feature_names(self) -> List[str]:
        """Return list of feature names."""
        return list(self.data.columns)
    
    def get_summary(self) -> Dict:
        """Return summary statistics."""
        return {
            "n_samples": self.shape[0],
            "n_features": self.shape[1],
            "feature_names": self.feature_names,
            "missing_count": self.data.isnull().sum().to_dict(),
            "dtype_info": self.data.dtypes.to_dict(),
        }
    
    def filter_by_date_range(self, start_date, end_date):
        """Filter data by date range."""
        if "date" not in self.data.columns:
            raise ValueError("DataFrame must have 'date' column")
        
        mask = (self.data["date"] >= start_date) & (self.data["date"] <= end_date)
        return FeatureSet(
            data=self.data[mask].reset_index(drop=True),
            metadata=self.metadata.copy(),
        )
    
    def remove_nan(self) -> "FeatureSet":
        """Remove rows with NaN values."""
        return FeatureSet(
            data=self.data.dropna().reset_index(drop=True),
            metadata=self.metadata.copy(),
        )
    
    def normalize(self) -> "FeatureSet":
        """Normalize features to [0, 1] range."""
        normalized_data = (self.data - self.data.min()) / (self.data.max() - self.data.min())
        return FeatureSet(
            data=normalized_data,
            metadata={**self.metadata, "normalized": True},
        )
    
    def to_dataframe(self) -> pd.DataFrame:
        """Export as pandas DataFrame."""
        return self.data.copy()
    
    def __len__(self):
        """Return number of samples."""
        return len(self.data)


@dataclass
class StockFeatureSet(FeatureSet):
    """
    Stock-specific feature set.
    
    Includes: daily returns, volatility, volume, anomalies, correlations.
    """
    
    def get_stock_features_summary(self) -> Dict:
        """Return summary of stock-specific features."""
        summary = self.get_summary()
        summary["stock_features"] = {
            "has_returns": "daily_return_pct" in self.feature_names,
            "has_volatility": "volatility_20d" in self.feature_names,
            "has_anomalies": "anomaly_flag" in self.feature_names,
        }
        return summary


@dataclass
class NewsFeatureSet(FeatureSet):
    """
    News-specific feature set.
    
    Includes: sentiment, frequency, TF-IDF, entities, mention counts.
    """
    
    def get_news_features_summary(self) -> Dict:
        """Return summary of news-specific features."""
        summary = self.get_summary()
        summary["news_features"] = {
            "has_sentiment": "sentiment_score" in self.feature_names,
            "has_frequency": "news_frequency" in self.feature_names,
            "has_tfidf": any("tfidf" in name.lower() for name in self.feature_names),
        }
        return summary
