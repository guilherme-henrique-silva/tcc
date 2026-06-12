"""ProcNewsRecord - registro de processamento de notícias (tabela PIPELINE_PROC_NEWS)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict


@dataclass(frozen=True)
class ProcNewsRecord:
    """Registro do processamento de uma notícia via Docling (Seção 8.4 do spec)."""

    url: str                # link da notícia (PK)
    ts_proc: datetime       # momento do processamento
    site_name: str          # nome do portal (ex.: G1, UOL)
    proc_success: bool      # sucesso/falha da conversão para Markdown

    def to_dict(self) -> Dict[str, object]:
        """Serializa o registro no formato das colunas da tabela (Rule 1)."""
        return {
            "URL": self.url,
            "TS_PROC": self.ts_proc.isoformat(),
            "NM_SITE": self.site_name,
            "PROC_SUCCESS": self.proc_success,
        }

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "ProcNewsRecord":
        """Reconstrói o registro a partir de uma linha da tabela (Rule 1)."""
        return cls(
            url=str(row["URL"]),
            ts_proc=cls._parse_timestamp(row["TS_PROC"]),
            site_name=str(row["NM_SITE"]) if row["NM_SITE"] is not None else "",
            proc_success=bool(row["PROC_SUCCESS"]),
        )

    @staticmethod
    def _parse_timestamp(value: object) -> datetime:
        """Parse do timestamp armazenado (Rule 1)."""
        if isinstance(value, datetime):
            return value

        return datetime.fromisoformat(str(value))
