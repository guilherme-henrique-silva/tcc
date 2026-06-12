"""Processors adapters."""

from .sentiment_analyzer_adapter import SentimentAnalyzerAdapter
from .entity_extractor_adapter import EntityExtractorAdapter
from .tfidf_adapter import TfIdfAdapter

__all__ = ["SentimentAnalyzerAdapter", "EntityExtractorAdapter", "TfIdfAdapter"]
