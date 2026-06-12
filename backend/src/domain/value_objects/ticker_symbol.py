"""TickerSymbol Value Object - Represents stock ticker symbols (e.g., BBAS3.SA)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TickerSymbol:
    """
    Immutable value object representing a stock ticker symbol.
    
    Examples: BBAS3.SA, ITUB4.SA, BBDC4.SA, SANB11.SA
    """
    
    value: str
    
    def __post_init__(self):
        """Validate ticker format."""
        self._validate()
    
    def _validate(self):
        """Validate ticker symbol format."""
        if not self.value:
            raise ValueError("Ticker symbol cannot be empty")
        
        if len(self.value) < 5:
            raise ValueError(f"Ticker symbol too short: {self.value}")
        
        if not self.value.isupper():
            raise ValueError(f"Ticker symbol must be uppercase: {self.value}")
    
    def __str__(self):
        """Return string representation."""
        return self.value
    
    def __eq__(self, other):
        """Compare ticker symbols."""
        if isinstance(other, TickerSymbol):
            return self.value == other.value
        return self.value == other
