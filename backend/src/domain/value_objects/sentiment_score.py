"""SentimentScore Value Object - Represents sentiment classification."""

from dataclasses import dataclass
from enum import IntEnum


class Sentiment(IntEnum):
    """Sentiment classification enumeration."""
    NEGATIVE = -1
    NEUTRAL = 0
    POSITIVE = 1


@dataclass(frozen=True)
class SentimentScore:
    """
    Immutable value object representing sentiment score.
    
    Restricted to {-1, 0, +1} representing {negative, neutral, positive}.
    """
    
    value: int
    
    def __post_init__(self):
        """Validate sentiment value."""
        self._validate()
    
    def _validate(self):
        """Ensure sentiment is one of allowed values."""
        allowed_values = {Sentiment.NEGATIVE, Sentiment.NEUTRAL, Sentiment.POSITIVE}
        
        if self.value not in allowed_values:
            raise ValueError(
                f"Sentiment score must be -1, 0, or +1. Got: {self.value}"
            )
    
    @property
    def is_positive(self) -> bool:
        """Check if sentiment is positive."""
        return self.value == Sentiment.POSITIVE
    
    @property
    def is_negative(self) -> bool:
        """Check if sentiment is negative."""
        return self.value == Sentiment.NEGATIVE
    
    @property
    def is_neutral(self) -> bool:
        """Check if sentiment is neutral."""
        return self.value == Sentiment.NEUTRAL
    
    def __str__(self):
        """Return string representation."""
        mapping = {
            Sentiment.NEGATIVE: "NEGATIVE",
            Sentiment.NEUTRAL: "NEUTRAL",
            Sentiment.POSITIVE: "POSITIVE",
        }
        return mapping[self.value]
