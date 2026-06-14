"""Modeling Preparation Service — preparação de datasets para modelagem."""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class UnsupervisedDataset:
    """Dataset prepared for unsupervised learning (clustering, PCA)."""
    
    features: np.ndarray
    feature_names: List[str]
    dates: List[str]


@dataclass(frozen=True)
class SupervisedDataset:
    """Dataset prepared for supervised learning (regression, classification)."""
    
    X: np.ndarray
    y: np.ndarray
    feature_names: List[str]
    dates: List[str]
    target_type: str  # "regression" or "classification"


@dataclass(frozen=True)
class TrainTestSplit:
    """Represents a single train/test split for walk-forward validation."""
    
    train_X: np.ndarray
    train_y: np.ndarray
    test_X: np.ndarray
    test_y: np.ndarray
    train_dates: List[str]
    test_dates: List[str]
    split_id: int


class ModelingPreparationService:
    """Service for preparing data for modeling."""
    
    def __init__(self):
        """Initialize service."""
        pass
    
    def prepare_unsupervised_data(
        self,
        stock_features: pd.DataFrame,
        news_features: pd.DataFrame,
    ) -> UnsupervisedDataset:
        """
        Prepare features for unsupervised learning (clustering, PCA).
        
        Uses: sentiment, frequency, volatility, volume
        """
        merged_df = self._merge_unsupervised_features(stock_features, news_features)
        
        if merged_df.empty:
            return self._create_empty_unsupervised_dataset()
        
        features_array = self._extract_unsupervised_features(merged_df)
        feature_names = self._get_unsupervised_feature_names()
        dates = self._extract_dates(merged_df)
        
        return UnsupervisedDataset(
            features=features_array,
            feature_names=feature_names,
            dates=dates,
        )
    
    def prepare_supervised_data(
        self,
        stock_features: pd.DataFrame,
        news_features: pd.DataFrame,
        control_variables: pd.DataFrame,
        target_prices: pd.DataFrame,
        classification: bool = False,
    ) -> SupervisedDataset:
        """
        Prepare features for supervised learning (regression or classification).
        
        Target: BBAS3 price variation (%)
        If classification: discretize to classes (Baixa, Normal, Alta)
        """
        merged_df = self._merge_supervised_features(
            stock_features,
            news_features,
            control_variables,
        )
        
        if merged_df.empty or target_prices.empty:
            return self._create_empty_supervised_dataset()
        
        X_array = self._extract_supervised_features(merged_df)
        y_array = self._extract_target(target_prices, classification)
        
        feature_names = self._get_supervised_feature_names()
        dates = self._extract_dates(merged_df)
        target_type = "classification" if classification else "regression"
        
        return SupervisedDataset(
            X=X_array,
            y=y_array,
            feature_names=feature_names,
            dates=dates,
            target_type=target_type,
        )
    
    def apply_walk_forward_split(
        self,
        dataset: SupervisedDataset,
        train_size: int = 180,
        test_size: int = 20,
    ) -> List[TrainTestSplit]:
        """
        Apply walk-forward validation without data leakage.
        
        Creates multiple train/test splits where test always follows training chronologically.
        """
        if len(dataset.X) < train_size + test_size:
            return []
        
        splits = []
        current_split_id = 0
        
        for start_idx in range(0, len(dataset.X) - train_size - test_size, test_size):
            split = self._create_walk_forward_split(
                dataset,
                start_idx,
                train_size,
                test_size,
                current_split_id,
            )
            splits.append(split)
            current_split_id += 1
        
        return splits
    
    def _merge_unsupervised_features(
        self,
        stock_features: pd.DataFrame,
        news_features: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge stock and news features for unsupervised learning (Rule 1)."""
        if stock_features.empty or news_features.empty:
            return pd.DataFrame()
        
        # Ensure date columns exist
        if "date" not in stock_features.columns:
            return pd.DataFrame()
        
        merged = stock_features.merge(
            news_features,
            on="date",
            how="outer",
        ).sort_values("date")
        
        return merged
    
    def _extract_unsupervised_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract unsupervised feature columns (Rule 1)."""
        feature_cols = self._get_unsupervised_feature_names()
        
        features_present = [col for col in feature_cols if col in df.columns]
        
        if not features_present:
            return np.array([])
        
        features_array = df[features_present].fillna(0.0).values
        return self._normalize_features(features_array)
    
    def _get_unsupervised_feature_names(self) -> List[str]:
        """Get list of unsupervised feature column names (Rule 1)."""
        return [
            "sentiment_score",
            "news_frequency",
            "volatility_20d",
            "volume_normalized",
        ]
    
    def _merge_supervised_features(
        self,
        stock_features: pd.DataFrame,
        news_features: pd.DataFrame,
        control_variables: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge all features for supervised learning (Rule 1)."""
        if stock_features.empty or news_features.empty:
            return pd.DataFrame()
        
        merged = stock_features.merge(
            news_features,
            on="date",
            how="outer",
        )
        
        if not control_variables.empty:
            merged = merged.merge(
                control_variables,
                on="date",
                how="outer",
            )
        
        merged = merged.sort_values("date")
        return merged
    
    def _extract_supervised_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract supervised feature columns with lags (Rule 1)."""
        feature_cols = self._get_supervised_feature_names()
        
        features_present = [col for col in feature_cols if col in df.columns]
        
        if not features_present:
            return np.array([]).reshape(0, len(feature_cols))
        
        features_df = df[features_present].fillna(0.0)
        
        # Add lagged features (t-1, t-2, t-3)
        lagged_features = self._add_lagged_features(features_df)
        
        return self._normalize_features(lagged_features.values)
    
    def _add_lagged_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add lagged versions of features (Rule 1)."""
        lagged = df.copy()
        
        for lag in [1, 2, 3]:
            for col in df.columns:
                lagged_col = f"{col}_lag{lag}"
                lagged[lagged_col] = df[col].shift(lag)
        
        return lagged.dropna()
    
    def _get_supervised_feature_names(self) -> List[str]:
        """Get list of supervised feature column names (Rule 1)."""
        base_features = [
            "sentiment_score",
            "news_frequency",
            "volatility_20d",
            "volume_normalized",
            "selic",
            "usd_brl",
        ]
        
        return base_features
    
    def _extract_target(
        self,
        target_prices: pd.DataFrame,
        classification: bool = False,
    ) -> np.ndarray:
        """Extract target variable for supervised learning (Rule 1)."""
        if target_prices.empty:
            return np.array([])
        
        if "daily_return_pct" not in target_prices.columns:
            return np.array([])
        
        targets = target_prices["daily_return_pct"].values
        
        if classification:
            return self._discretize_targets(targets)
        
        return targets
    
    def _discretize_targets(self, targets: np.ndarray) -> np.ndarray:
        """Convert regression targets to classification classes (Rule 1)."""
        # Classes: 0=Baixa (<-2%), 1=Normal ([-2%, +2%]), 2=Alta (>+2%)
        classes = np.zeros(len(targets), dtype=int)
        
        classes[targets < -2.0] = 0  # Baixa
        classes[(targets >= -2.0) & (targets <= 2.0)] = 1  # Normal
        classes[targets > 2.0] = 2  # Alta
        
        return classes
    
    def _extract_dates(self, df: pd.DataFrame) -> List[str]:
        """Extract dates from dataframe (Rule 1)."""
        if "date" not in df.columns:
            return []
        
        return df["date"].astype(str).tolist()
    
    def _normalize_features(self, features: np.ndarray) -> np.ndarray:
        """Normalize features to 0-1 scale per column (Rule 1)."""
        if features.size == 0:
            return features
        
        min_vals = np.nanmin(features, axis=0)
        max_vals = np.nanmax(features, axis=0)
        
        # Avoid division by zero
        ranges = np.where(max_vals == min_vals, 1.0, max_vals - min_vals)
        
        normalized = (features - min_vals) / ranges
        
        # Replace NaN and inf with 0
        normalized = np.nan_to_num(normalized, nan=0.0, posinf=0.0, neginf=0.0)
        
        return normalized
    
    def _create_walk_forward_split(
        self,
        dataset: SupervisedDataset,
        start_idx: int,
        train_size: int,
        test_size: int,
        split_id: int,
    ) -> TrainTestSplit:
        """Create a single walk-forward split (Rule 1)."""
        train_end_idx = start_idx + train_size
        test_end_idx = train_end_idx + test_size
        
        train_X = dataset.X[start_idx:train_end_idx]
        train_y = dataset.y[start_idx:train_end_idx]
        test_X = dataset.X[train_end_idx:test_end_idx]
        test_y = dataset.y[train_end_idx:test_end_idx]
        
        train_dates = dataset.dates[start_idx:train_end_idx]
        test_dates = dataset.dates[train_end_idx:test_end_idx]
        
        return TrainTestSplit(
            train_X=train_X,
            train_y=train_y,
            test_X=test_X,
            test_y=test_y,
            train_dates=train_dates,
            test_dates=test_dates,
            split_id=split_id,
        )
    
    def _create_empty_unsupervised_dataset(self) -> UnsupervisedDataset:
        """Create empty unsupervised dataset (Rule 2: no else)."""
        return UnsupervisedDataset(
            features=np.array([]),
            feature_names=[],
            dates=[],
        )
    
    def _create_empty_supervised_dataset(self) -> SupervisedDataset:
        """Create empty supervised dataset (Rule 2: no else)."""
        return SupervisedDataset(
            X=np.array([]),
            y=np.array([]),
            feature_names=[],
            dates=[],
            target_type="regression",
        )
