"""MacroeconomicIndicator Entity - Represents macro indicators."""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class MacroeconomicIndicator:
    """
    Entity representing a macroeconomic indicator value.
    
    Attributes:
        indicator_name: Name of indicator (Selic, USD/BRL, Soja, etc)
        date: Date of measurement
        value: Indicator value
        unit: Unit of measurement (%, USD, price per unit, etc)
        source: Data source
    """
    
    indicator_name: str
    date: date
    value: float
    unit: str
    source: str
    metadata: Optional[dict] = None
    
    def __post_init__(self):
        """Validate indicator data."""
        self._validate()
    
    def _validate(self):
        """Ensure indicator fields are valid."""
        if not self.indicator_name or not self.indicator_name.strip():
            raise ValueError("Indicator name cannot be empty")
        
        if self.value is None:
            raise ValueError("Indicator value cannot be None")
        
        if not self.unit or not self.unit.strip():
            raise ValueError("Unit cannot be empty")
    
    def __str__(self):
        """Return string representation."""
        return f"{self.indicator_name} ({self.date}): {self.value} {self.unit}"
