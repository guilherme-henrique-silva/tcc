"""TickerSymbol Value Object - Represents market symbols (e.g., BBAS3.SA, ^BVSP, ZS=F)."""

import re
from dataclasses import dataclass

# Ação com sufixo de bolsa (BBAS3.SA), índice (^BVSP) ou contrato futuro (ZS=F).
_TICKER_PATTERN = re.compile(r"^\^?[A-Z0-9]{1,10}(\.[A-Z]{1,3}|=F)?$")


@dataclass(frozen=True)
class TickerSymbol:
    """
    Immutable value object representing a market symbol.

    Examples: BBAS3.SA, ITUB4.SA, SANB11.SA, ^BVSP, ZS=F
    """

    value: str

    def __post_init__(self):
        """Validate ticker format."""
        self._validate()

    def _validate(self):
        """Validate ticker symbol format."""
        if not self.value:
            raise ValueError("Ticker symbol cannot be empty")

        if self.value != self.value.upper():
            raise ValueError(f"Ticker symbol must be uppercase: {self.value}")

        if not _TICKER_PATTERN.fullmatch(self.value):
            raise ValueError(f"Invalid ticker symbol format: {self.value}")

    def __str__(self):
        """Return string representation."""
        return self.value

    def __eq__(self, other):
        """Compare ticker symbols."""
        if isinstance(other, TickerSymbol):
            return self.value == other.value
        return self.value == other
