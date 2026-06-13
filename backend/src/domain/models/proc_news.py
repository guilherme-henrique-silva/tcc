"""ProcNewsRecord - registro de processamento de notícias (tabela PIPELINE_PROC_NEWS)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass(frozen=True)
class ProcNewsRecord:
    """Registro do processamento de uma notícia via Docling (Seção 9 do spec)."""

    url: str                          # link da notícia (PK)
    proc_ts: datetime                 # momento do processamento
    site_name: str                    # nome do portal (ex.: G1, UOL)
    proc_success: bool                # sucesso/falha da conversão para Markdown
    proc_id: Optional[str] = None     # uuid da execução (FK lógica p/ PIPELINE_PROC_ID)

    def to_dict(self) -> Dict[str, object]:
        """Serializa o registro no formato das colunas da tabela (Rule 1)."""
        return {
            "URL": self.url,
            "PROC_ID": self.proc_id,
            "PROC_TS": self.proc_ts.isoformat(),
            "NM_SITE": self.site_name,
            "PROC_SUCCESS": self.proc_success,
        }

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "ProcNewsRecord":
        """Reconstrói o registro a partir de uma linha da tabela (Rule 1)."""
        proc_id = row.get("PROC_ID")
        return cls(
            url=str(row["URL"]),
            proc_ts=cls._parse_timestamp(row["PROC_TS"]),
            site_name=str(row["NM_SITE"]) if row["NM_SITE"] is not None else "",
            proc_success=bool(row["PROC_SUCCESS"]),
            proc_id=str(proc_id) if proc_id is not None else None,
        )

    @staticmethod
    def _parse_timestamp(value: object) -> datetime:
        """Parse do timestamp armazenado (Rule 1)."""
        if isinstance(value, datetime):
            return value

        return datetime.fromisoformat(str(value))
