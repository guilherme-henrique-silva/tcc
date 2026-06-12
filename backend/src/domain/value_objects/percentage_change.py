"""PercentageChange Value Object - Represents percentage variation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PercentageChange:
    """
    Immutable value object representing percentage change.
    
    Range: [-100, +100] representing -100% to +100% change.
    """
    
    value: float
    
    def __post_init__(self):
        """Validate percentage range."""
        self._validate()
    
    def _validate(self):
        """Ensure percentage is within valid range."""
        if not (-100 <= self.value <= 100):
            raise ValueError(
                f"Percentage change must be in range [-100, 100]. Got: {self.value}"
            )
    
    @property
    def is_positive(self) -> bool:
        """Check if change is positive."""
        return self.value > 0
    
    @property
    def is_negative(self) -> bool:
        """Check if change is negative."""
        return self.value < 0
    
    @property
    def is_stable(self) -> bool:
        """Check if change is approximately zero."""
        return abs(self.value) < 0.01
    
    def __str__(self):
        """Return formatted percentage string."""
        return f"{self.value:.2f}%"
