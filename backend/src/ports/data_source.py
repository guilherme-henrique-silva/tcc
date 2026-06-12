"""Port Interfaces - Define contracts for adapters (Hexagonal Architecture)."""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional, Dict
import pandas as pd

from src.domain.models import StockPrice, News, MacroeconomicIndicator
from src.domain.value_objects import TickerSymbol, DateRange


class DataSourcePort(ABC):
    """Interface for data source adapters."""
    
    @abstractmethod
    def get_stock_prices(
        self,
        ticker: TickerSymbol,
        date_range: DateRange,
    ) -> List[StockPrice]:
        """
        Fetch stock prices.
        
        Args:
            ticker: Stock ticker symbol
            date_range: Date interval
            
        Returns:
            List of StockPrice entities
        """
        pass
    
    @abstractmethod
    def get_news(
        self,
        date_range: DateRange,
    ) -> List[News]:
        """
        Fetch news articles.
        
        Args:
            date_range: Date interval
            
        Returns:
            List of News entities
        """
        pass
    
    @abstractmethod
    def get_macroeconomic_data(
        self,
        indicators: List[str],
        date_range: DateRange,
    ) -> List[MacroeconomicIndicator]:
        """
        Fetch macroeconomic indicators (Tópico 2.5).
        
        Args:
            indicators: List of indicator names (Selic, USD/BRL, etc)
            date_range: Date interval
            
        Returns:
            List of MacroeconomicIndicator entities
        """
        pass


class StoragePort(ABC):
    """Interface for storage adapters."""
    
    @abstractmethod
    def save_features(
        self,
        features_data: pd.DataFrame,
        dataset_id: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Save feature dataset.
        
        Args:
            features_data: DataFrame with features
            dataset_id: Unique identifier for dataset
            metadata: Optional metadata
        """
        pass
    
    @abstractmethod
    def load_features(self, dataset_id: str) -> pd.DataFrame:
        """
        Load feature dataset.
        
        Args:
            dataset_id: Dataset identifier
            
        Returns:
            DataFrame with features
        """
        pass
    
    @abstractmethod
    def save_validation_results(
        self,
        results: Dict,
        dataset_id: str,
    ) -> None:
        """Save validation results."""
        pass
    
    @abstractmethod
    def save_granger_test_results(
        self,
        results: Dict,
        dataset_id: str,
    ) -> None:
        """Save Granger test results (Tópico 2.5)."""
        pass


class NewsProcessorPort(ABC):
    """Interface for news processing adapters."""
    
    @abstractmethod
    def analyze_sentiment(self, text: str) -> int:
        """
        Analyze sentiment of text.
        
        Returns:
            -1 (negative), 0 (neutral), 1 (positive)
        """
        pass
    
    @abstractmethod
    def extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text."""
        pass
    
    @abstractmethod
    def calculate_tfidf(
        self,
        documents: List[str],
        n_components: int = 20,
    ) -> pd.DataFrame:
        """Calculate TF-IDF features."""
        pass
