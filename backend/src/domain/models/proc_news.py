"""ProcNewsRecord - registro de processamento de notícias (tabela PIPELINE_PROC_NEWS)."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Optional


@dataclass(frozen=True)
class ProcNewsRecord:
    """Registro do processamento de uma notícia via Docling."""

    url: str                          # link da notícia (PK)
    proc_ts: datetime                 # momento do processamento
    site_name: str                    # nome do portal (ex.: G1, UOL)
    proc_success: bool                # sucesso/falha da conversão para Markdown
    proc_id: Optional[str] = None     # uuid da execução (FK lógica p/ PIPELINE_PROC_ID)
    news_date: Optional[date] = None  # data de publicação informada pelo usuário

    def to_dict(self) -> Dict[str, object]:
        """Serializa o registro no formato das colunas da tabela."""
        return {
            "URL": self.url,
            "PROC_ID": self.proc_id,
            "PROC_TS": self.proc_ts.isoformat(),
            "NM_SITE": self.site_name,
            "PROC_SUCCESS": self.proc_success,
            "NEWS_DATE": self.news_date.isoformat() if self.news_date else None,
        }

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "ProcNewsRecord":
        """Reconstrói o registro a partir de uma linha da tabela."""
        proc_id = row.get("PROC_ID")
        news_date = row.get("NEWS_DATE")
        return cls(
            url=str(row["URL"]),
            proc_ts=cls._parse_timestamp(row["PROC_TS"]),
            site_name=str(row["NM_SITE"]) if row["NM_SITE"] is not None else "",
            proc_success=bool(row["PROC_SUCCESS"]),
            proc_id=str(proc_id) if proc_id is not None else None,
            news_date=date.fromisoformat(str(news_date)) if news_date else None,
        )

    @staticmethod
    def _parse_timestamp(value: object) -> datetime:
        """Parse do timestamp armazenado."""
        if isinstance(value, datetime):
            return value

        return datetime.fromisoformat(str(value))
