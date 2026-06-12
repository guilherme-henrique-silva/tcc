"""News Entity - Represents a news article."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from ..value_objects import SentimentScore


@dataclass
class News:
    """
    Entity representing a news article.
    
    Attributes:
        title: News headline
        content: News body/content
        source: News source (G1, UOL, CNN Brasil, etc)
        published_date: Publication date
        url: Source URL
        sentiment_score: Optional sentiment analysis result
        entities: Optional extracted named entities
    """
    
    title: str
    content: str
    source: str
    published_date: datetime
    url: str
    sentiment_score: Optional[SentimentScore] = None
    entities: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate news data."""
        self._validate()
    
    def _validate(self):
        """Ensure required fields are valid."""
        if not self.title or not self.title.strip():
            raise ValueError("Title cannot be empty")
        
        if not self.content or not self.content.strip():
            raise ValueError("Content cannot be empty")
        
        if not self.source or not self.source.strip():
            raise ValueError("Source cannot be empty")
        
        if not self.url or not self.url.strip():
            raise ValueError("URL cannot be empty")
    
    def set_sentiment(self, sentiment: SentimentScore):
        """Set sentiment score for news."""
        self.sentiment_score = sentiment
    
    def add_entity(self, entity: str):
        """Add extracted entity."""
        if entity not in self.entities:
            self.entities.append(entity)
    
    @property
    def word_count(self) -> int:
        """Return word count of content."""
        return len(self.content.split())
    
    def __str__(self):
        """Return string representation."""
        return f"{self.source} ({self.published_date.date()}): {self.title}"
