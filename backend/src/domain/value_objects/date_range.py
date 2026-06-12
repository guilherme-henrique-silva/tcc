"""DateRange Value Object - Represents time interval."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DateRange:
    """
    Immutable value object representing a date interval.
    
    Ensures start_date <= end_date.
    """
    
    start_date: date
    end_date: date
    
    def __post_init__(self):
        """Validate date range."""
        self._validate()
    
    def _validate(self):
        """Ensure start_date is before or equal to end_date."""
        if self.start_date > self.end_date:
            raise ValueError(
                f"start_date ({self.start_date}) must be <= end_date ({self.end_date})"
            )
    
    @property
    def days_count(self) -> int:
        """Return number of days in range."""
        return (self.end_date - self.start_date).days + 1
    
    def contains(self, target_date: date) -> bool:
        """Check if date falls within range."""
        return self.start_date <= target_date <= self.end_date
    
    def __str__(self):
        """Return string representation."""
        return f"{self.start_date} to {self.end_date}"
