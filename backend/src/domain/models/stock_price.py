"""StockPrice Entity - Represents a stock price data point."""

from dataclasses import dataclass
from datetime import date

from ..value_objects import TickerSymbol


@dataclass
class StockPrice:
    """
    Entity representing a stock price record.
    
    Attributes:
        ticker: Stock ticker symbol (e.g., BBAS3.SA)
        date: Trading date
        open_price: Opening price
        close_price: Closing price
        high_price: Highest price of the day
        low_price: Lowest price of the day
        volume: Trading volume
    """
    
    ticker: TickerSymbol
    date: date
    open_price: float
    close_price: float
    high_price: float
    low_price: float
    volume: int
    
    def __post_init__(self):
        """Validate price consistency."""
        self._validate()
    
    def _validate(self):
        """Ensure price relationships are valid."""
        if not (self.low_price <= self.open_price <= self.high_price):
            raise ValueError("Open price must be between low and high")
        
        if not (self.low_price <= self.close_price <= self.high_price):
            raise ValueError("Close price must be between low and high")
        
        if self.low_price > self.high_price:
            raise ValueError("Low price cannot be greater than high price")
        
        if self.volume < 0:
            raise ValueError("Volume cannot be negative")
    
    @property
    def daily_return_percentage(self) -> float:
        """Calculate daily return percentage."""
        if self.open_price == 0:
            return 0.0
        
        return ((self.close_price - self.open_price) / self.open_price) * 100
    
    @property
    def daily_high_low_spread(self) -> float:
        """Calculate spread between high and low."""
        return self.high_price - self.low_price
    
    def __str__(self):
        """Return string representation."""
        return f"{self.ticker} ({self.date}): ${self.close_price:.2f}"
