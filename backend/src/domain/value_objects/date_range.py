"""DateRange — value object imutável para intervalos de data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List


@dataclass(frozen=True)
class DateRange:
    """Intervalo de datas imutável.

    Garante start_date <= end_date. Para períodos >= 1 ano use split() para
    gerar sub-intervalos antes de chamadas a APIs com limitação de período.
    """

    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError(
                f"start_date ({self.start_date}) deve ser <= end_date ({self.end_date})"
            )

    @property
    def days_count(self) -> int:
        """Número de dias no intervalo (inclusivo)."""
        return (self.end_date - self.start_date).days + 1

    def contains(self, target_date: date) -> bool:
        """Verifica se a data está dentro do intervalo."""
        return self.start_date <= target_date <= self.end_date

    def split(self, max_days: int = 365) -> List["DateRange"]:
        """Divide o intervalo em janelas de até max_days dias (sem sobreposição).

        Para períodos menores que max_days retorna uma lista com o próprio objeto.
        Cada janela é inclusiva e as janelas somadas cobrem todo o intervalo original.
        """
        if self.days_count <= max_days:
            return [self]

        chunks: List[DateRange] = []
        cursor = self.start_date

        while cursor <= self.end_date:
            chunk_end = min(cursor + timedelta(days=max_days - 1), self.end_date)
            chunks.append(DateRange(cursor, chunk_end))
            cursor = chunk_end + timedelta(days=1)

        return chunks

    def __str__(self) -> str:
        return f"{self.start_date} a {self.end_date}"
