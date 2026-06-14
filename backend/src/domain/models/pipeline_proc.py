"""PipelineProcRecord - registro de uma execução da pipeline (tabela PIPELINE_PROC_ID)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass(frozen=True)
class PipelineProcRecord:
    """Registro de uma execução da pipeline identificada por UUID."""

    proc_id: str                       # uuid da execução (PK)
    proc_ts_start: datetime            # início da execução
    proc_ts_end: Optional[datetime] = None  # fim da execução (None enquanto roda)

    def to_dict(self) -> Dict[str, object]:
        """Serializa o registro no formato das colunas da tabela (Rule 1)."""
        return {
            "PROC_ID": self.proc_id,
            "PROC_TS_START": self.proc_ts_start.isoformat(),
            "PROC_TS_END": self.proc_ts_end.isoformat() if self.proc_ts_end else None,
        }

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "PipelineProcRecord":
        """Reconstrói o registro a partir de uma linha da tabela (Rule 1)."""
        return cls(
            proc_id=str(row["PROC_ID"]),
            proc_ts_start=cls._parse_timestamp(row["PROC_TS_START"]),
            proc_ts_end=cls._parse_optional_timestamp(row.get("PROC_TS_END")),
        )

    @staticmethod
    def _parse_timestamp(value: object) -> datetime:
        """Parse do timestamp armazenado (Rule 1)."""
        if isinstance(value, datetime):
            return value

        return datetime.fromisoformat(str(value))

    @classmethod
    def _parse_optional_timestamp(cls, value: object) -> Optional[datetime]:
        """Parse de um timestamp que pode ser NULL (execução em andamento)."""
        if value is None:
            return None

        return cls._parse_timestamp(value)
