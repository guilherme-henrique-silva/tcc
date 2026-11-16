"""PipelineProcRecord - registro de uma execução da pipeline (tabela PIPELINE_PROC_ID)."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Optional

STATUS_RUNNING = "RUNNING"
STATUS_FAILED = "FAILED"


@dataclass(frozen=True)
class PipelineProcRecord:
    """Registro de uma execução da pipeline identificada por UUID.

    Além dos timestamps, guarda o que é preciso para **recarregar** a execução depois de
    uma reinicialização dos serviços: o período analisado, o status final e dois blocos
    JSON — ``request`` (entradas: etapas habilitadas, links de notícias, tratamento via
    LLM) e ``result`` (saídas: resultado por etapa, erro, URLs pendentes).
    """

    proc_id: str                       # uuid da execução (PK)
    proc_ts_start: datetime            # início da execução
    proc_ts_end: Optional[datetime] = None  # fim da execução (None enquanto roda)
    status: Optional[str] = None       # RUNNING/SUCCESS/FAILED/BLOCKED; None em execuções antigas
    date_start: Optional[date] = None  # início do período analisado
    date_end: Optional[date] = None    # fim do período analisado
    request: Optional[Dict[str, Any]] = None  # entradas da execução
    result: Optional[Dict[str, Any]] = None   # saídas da execução

    def to_dict(self) -> Dict[str, object]:
        """Serializa o registro no formato das colunas da tabela."""
        return {
            "PROC_ID": self.proc_id,
            "PROC_TS_START": self.proc_ts_start.isoformat(),
            "PROC_TS_END": self.proc_ts_end.isoformat() if self.proc_ts_end else None,
            "STATUS": self.status,
            "DATE_START": self.date_start.isoformat() if self.date_start else None,
            "DATE_END": self.date_end.isoformat() if self.date_end else None,
            "REQUEST": self.request,
            "RESULT": self.result,
        }

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "PipelineProcRecord":
        """Reconstrói o registro a partir de uma linha da tabela.

        ``REQUEST`` e ``RESULT`` já chegam como dict (o adapter faz o parse do JSON).
        """
        return cls(
            proc_id=str(row["PROC_ID"]),
            proc_ts_start=cls._parse_timestamp(row["PROC_TS_START"]),
            proc_ts_end=cls._parse_optional_timestamp(row.get("PROC_TS_END")),
            status=row.get("STATUS"),
            date_start=cls._parse_optional_date(row.get("DATE_START")),
            date_end=cls._parse_optional_date(row.get("DATE_END")),
            request=row.get("REQUEST"),
            result=row.get("RESULT"),
        )

    @staticmethod
    def _parse_timestamp(value: object) -> datetime:
        """Parse do timestamp armazenado."""
        if isinstance(value, datetime):
            return value

        return datetime.fromisoformat(str(value))

    @classmethod
    def _parse_optional_timestamp(cls, value: object) -> Optional[datetime]:
        """Parse de um timestamp que pode ser NULL (execução em andamento)."""
        if value is None:
            return None

        return cls._parse_timestamp(value)

    @staticmethod
    def _parse_optional_date(value: object) -> Optional[date]:
        """Parse de uma data ISO que pode ser NULL (execuções anteriores a esta coluna)."""
        if not value:
            return None

        return date.fromisoformat(str(value))
