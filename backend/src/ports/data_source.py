"""Port Interfaces - Define contracts for adapters (Hexagonal Architecture)."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict
import pandas as pd

from src.domain.models import (
    StockPrice,
    News,
    MacroeconomicIndicator,
    ProcNewsRecord,
    PipelineProcRecord,
    TreatedNewsRecord,
)
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
    """Interface for storage adapters (alinhada à implementação real — Achado 4)."""

    @abstractmethod
    def save_features(self, features: pd.DataFrame, dataset_id: str) -> None:
        """Save feature dataset under the given identifier."""
        pass

    @abstractmethod
    def load_features(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Load a feature dataset, or None when absent."""
        pass

    @abstractmethod
    def save_validation_results(self, results: Dict) -> None:
        """Save validation results."""
        pass

    @abstractmethod
    def save_granger_test_results(self, results: Dict) -> None:
        """Save Granger test results (Tópico 2.5)."""
        pass

    # --- Rastreabilidade de execução (Seção 9 do spec) ----------------------

    @abstractmethod
    def save_proc_news(self, record: ProcNewsRecord) -> None:
        """Persist a PIPELINE_PROC_NEWS row for a processed link."""
        pass

    @abstractmethod
    def get_proc_news(self, url: str) -> Optional[ProcNewsRecord]:
        """Retrieve a PIPELINE_PROC_NEWS record by URL, or None."""
        pass

    @abstractmethod
    def save_pipeline_proc(self, record: PipelineProcRecord) -> None:
        """Persist a PIPELINE_PROC_ID row at the start of an execution."""
        pass

    @abstractmethod
    def finish_pipeline_proc(self, proc_id: str, end_ts: datetime) -> None:
        """Stamp PROC_TS_END on the PIPELINE_PROC_ID row when execution ends."""
        pass

    # --- Documentos tratados (Seção 10 do spec) -----------------------------

    @abstractmethod
    def save_treated_news(self, record: TreatedNewsRecord) -> None:
        """Persist a treated news document with its frontmatter metadata."""
        pass

    @abstractmethod
    def get_treated_news(self, url: str) -> Optional[TreatedNewsRecord]:
        """Retrieve a treated news document by URL, or None."""
        pass

    @abstractmethod
    def list_treated_news(self, proc_id: str) -> List[TreatedNewsRecord]:
        """List treated documents associated with a pipeline execution."""
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
