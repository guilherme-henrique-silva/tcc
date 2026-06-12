"""Sentiment Analysis Adapter using Transformers."""

from typing import Optional

from src.domain.value_objects import SentimentScore
from src.ports.data_source import NewsProcessorPort


class SentimentAnalyzerAdapter(NewsProcessorPort):
    """Adapter for sentiment analysis using transformers BERT model (Rule 7: small entity)."""
    
    def __init__(self):
        """Initialize sentiment analyzer."""
        self.model = self._load_model()
    
    def analyze_sentiment(self, text: str) -> Optional[SentimentScore]:
        """Analyze sentiment of text using BERT model."""
        try:
            if not text or not isinstance(text, str):
                return None
            
            clean_text = self._preprocess_text(text)
            
            if not clean_text:
                return None
            
            sentiment_label = self._predict_sentiment(clean_text)
            return self._convert_to_sentiment_score(sentiment_label)
        
        except Exception:
            return None
    
    def extract_entities(self, text: str) -> set:
        """Extract entities from text (delegated to EntityExtractorAdapter)."""
        return set()
    
    def calculate_tfidf(self, documents: list, n_components: int) -> None:
        """Calculate TF-IDF (delegated to TfIdfAdapter)."""
        pass
    
    def _load_model(self):
        """Load pre-trained sentiment model (Rule 1)."""
        try:
            from transformers import pipeline
            
            # Using multilingual BERT for Portuguese
            return pipeline(
                "sentiment-analysis",
                model="nlptown/bert-base-multilingual-uncased-sentiment",
            )
        
        except ImportError:
            return None
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for sentiment analysis (Rule 1)."""
        if not text:
            return ""
        
        clean_text = text.strip()
        
        # Limit length for model
        if len(clean_text) > 512:
            clean_text = clean_text[:512]
        
        return clean_text
    
    def _predict_sentiment(self, text: str) -> str:
        """Predict sentiment using model (Rule 1)."""
        if not self.model:
            return "NEUTRAL"
        
        try:
            results = self.model(text)
            
            if not results:
                return "NEUTRAL"
            
            top_result = results[0]
            label = top_result.get("label", "").upper()
            
            return self._simplify_sentiment_label(label)
        
        except Exception:
            return "NEUTRAL"
    
    def _simplify_sentiment_label(self, label: str) -> str:
        """Convert model label to simple sentiment (Rule 1)."""
        label_lower = label.lower()
        
        if "negative" in label_lower or "1 star" in label_lower or "2 star" in label_lower:
            return "NEGATIVE"
        
        if "positive" in label_lower or "4 star" in label_lower or "5 star" in label_lower:
            return "POSITIVE"
        
        return "NEUTRAL"
    
    def _convert_to_sentiment_score(self, label: str) -> SentimentScore:
        """Convert label to SentimentScore domain model (Rule 1)."""
        if label == "NEGATIVE":
            return SentimentScore(value=-1)
        elif label == "POSITIVE":
            return SentimentScore(value=1)
        else:
            return SentimentScore(value=0)
