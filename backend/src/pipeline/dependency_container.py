"""Dependency Injection Container for pipeline orchestration."""

from typing import List, Dict, Any, Optional

from src.ports.data_source import DataSourcePort, StoragePort, NewsProcessorPort
from src.adapters.data_sources import YFinanceAdapter, CsvNewsAdapter, BcbApiAdapter
from src.adapters.storage import SQLiteStorage, CsvStorage
from src.adapters.processors import SentimentAnalyzerAdapter, EntityExtractorAdapter, TfIdfAdapter
from src.adapters.processors.docling_converter_adapter import DoclingConverterAdapter
from app.core.config import Config


class DependencyContainer:
    """Manages dependency injection for all adapters and services (Rule 7: small entity)."""
    
    def __init__(self, config: Config = None):
        """Initialize container with optional configuration."""
        self.config = config or Config()
        self._data_source_adapter: Optional[DataSourcePort] = None
        self._storage_adapter: Optional[StoragePort] = None
        self._docling_converter: Optional[DoclingConverterAdapter] = None
        self._bcb_adapter: Optional[BcbApiAdapter] = None
        self._processors: Dict[str, NewsProcessorPort] = {}

    def get_data_source(self) -> DataSourcePort:
        """Get data source adapter (singleton pattern)."""
        if not self._data_source_adapter:
            self._data_source_adapter = self._create_data_source_adapter()
        
        return self._data_source_adapter
    
    def get_storage(self) -> StoragePort:
        """Get storage adapter (singleton pattern)."""
        if not self._storage_adapter:
            self._storage_adapter = self._create_storage_adapter()
        
        return self._storage_adapter
    
    def get_sentiment_analyzer(self) -> NewsProcessorPort:
        """Get sentiment analyzer processor."""
        if "sentiment" not in self._processors:
            self._processors["sentiment"] = SentimentAnalyzerAdapter()
        
        return self._processors["sentiment"]
    
    def get_entity_extractor(self) -> NewsProcessorPort:
        """Get entity extractor processor."""
        if "entities" not in self._processors:
            self._processors["entities"] = EntityExtractorAdapter()
        
        return self._processors["entities"]
    
    def get_tfidf_processor(self) -> NewsProcessorPort:
        """Get TF-IDF processor."""
        if "tfidf" not in self._processors:
            self._processors["tfidf"] = TfIdfAdapter()

        return self._processors["tfidf"]

    def get_docling_converter(self) -> DoclingConverterAdapter:
        """Get Docling converter wrapper (singleton pattern)."""
        if not self._docling_converter:
            self._docling_converter = DoclingConverterAdapter()

        return self._docling_converter

    def get_bcb_adapter(self) -> BcbApiAdapter:
        """Get Banco Central API adapter (singleton pattern)."""
        if not self._bcb_adapter:
            self._bcb_adapter = BcbApiAdapter(self.config)

        return self._bcb_adapter
    
    def _create_data_source_adapter(self) -> DataSourcePort:
        """Create data source adapter instance (Rule 1)."""
        # Default: YFinanceAdapter for production
        return YFinanceAdapter()
    
    def _create_storage_adapter(self) -> StoragePort:
        """Create storage adapter instance (Rule 1)."""
        database_url = self.config.DATABASE_URL
        return SQLiteStorage(database_url)
    
    def reset_singletons(self) -> None:
        """Reset all singleton instances (Rule 1)."""
        self._data_source_adapter = None
        self._storage_adapter = None
        self._docling_converter = None
        self._bcb_adapter = None
        self._processors.clear()
