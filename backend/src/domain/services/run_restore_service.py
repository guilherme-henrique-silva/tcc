"""RunRestoreService - recarrega o estado de uma execução já iniciada da pipeline.

Quando os microsserviços são parados e reiniciados, a sessão do frontend começa vazia. Tudo
o que é necessário para reconstruí-la está no banco (volume `data/`): a execução em
`PIPELINE_PROC_ID`, as notícias em `PIPELINE_PROC_NEWS`, os documentos tratados em
`PIPELINE_TREATED_NEWS` e o relatório em `granger_results`. Este serviço apenas **lê** e
monta o estado; nada é recalculado nem reexecutado.
"""

from typing import Any, Dict, List, Optional

from src.domain.models import PipelineProcRecord, ProcNewsRecord
from src.ports.data_source import StoragePort

# Status exibido para execuções gravadas antes de existir a coluna STATUS.
STATUS_UNKNOWN = "UNKNOWN"

# Status finais que o frontend sabe renderizar como resultado de execução.
_RENDERABLE_RESULT_STATUSES = frozenset({"SUCCESS", "FAILED", "BLOCKED"})


class RunRestoreService:
    """Lê do storage o histórico de execuções e o estado completo de cada uma."""

    def __init__(self, storage: StoragePort):
        """Initialize with the storage port that holds the persisted runs."""
        self._storage = storage

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Resumo das execuções mais recentes (mais nova primeiro)."""
        records = self._storage.list_pipeline_procs(limit)

        return [self._summary(record) for record in records]

    def get_run(self, proc_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Estado completo de uma execução; a mais recente quando ``proc_id`` é None.

        Devolve None quando não há execução (banco vazio ou id desconhecido).
        """
        record = self._find(proc_id)

        if record is None:
            return None

        news_links = self._news_links(record)

        return {
            **self._summary(record, news_links),
            "enabled_stages": (record.request or {}).get("enabled_stages"),
            "news_links": news_links,
            "treated_news": self._treated_news(news_links),
            "run_result": self._run_result(record),
            "has_granger_report": self._has_granger_report(record.proc_id),
        }

    def _find(self, proc_id: Optional[str]) -> Optional[PipelineProcRecord]:
        """Execução pedida, ou a mais recente quando nenhum id é informado."""
        if proc_id:
            return self._storage.get_pipeline_proc(proc_id)

        latest = self._storage.list_pipeline_procs(1)
        return latest[0] if latest else None

    def _summary(
        self,
        record: PipelineProcRecord,
        news_links: Optional[Dict[str, list]] = None,
    ) -> Dict[str, Any]:
        """Campos de listagem de uma execução."""
        links = self._news_links(record) if news_links is None else news_links

        return {
            "proc_id": record.proc_id,
            "status": record.status or STATUS_UNKNOWN,
            "started_at": record.proc_ts_start.isoformat(),
            "finished_at": record.proc_ts_end.isoformat() if record.proc_ts_end else None,
            "date_start": record.date_start.isoformat() if record.date_start else None,
            "date_end": record.date_end.isoformat() if record.date_end else None,
            "news_links_count": sum(len(items) for items in links.values()),
        }

    def _news_links(self, record: PipelineProcRecord) -> Dict[str, list]:
        """Links da execução agrupados por data de publicação.

        Usa os links gravados no início da execução; execuções antigas (sem `REQUEST`)
        são reconstruídas a partir de `PIPELINE_PROC_NEWS`.
        """
        saved = (record.request or {}).get("news_links")

        if saved:
            return saved

        return self._links_from_proc_news(record.proc_id)

    def _links_from_proc_news(self, proc_id: str) -> Dict[str, list]:
        """Reagrupa por data as notícias processadas com este `PROC_ID`.

        Uma URL reprocessada por execução posterior passa a carregar o `PROC_ID` mais
        novo, então este é o melhor esforço para execuções anteriores ao registro do
        `REQUEST`. Linhas sem data de publicação não têm grupo e ficam de fora.
        """
        groups: Dict[str, list] = {}

        for news in self._storage.list_proc_news_by_proc_id(proc_id):
            if news.news_date is None:
                continue

            groups.setdefault(news.news_date.isoformat(), []).append(self._link_item(news))

        return groups

    @staticmethod
    def _link_item(news: ProcNewsRecord):
        """Item de link no formato do upload: URL pura ou `{"url", "time"}`."""
        if news.news_time is None:
            return news.url

        return {"url": news.url, "time": news.news_time.strftime("%H:%M")}

    def _treated_news(self, news_links: Dict[str, list]) -> Dict[str, str]:
        """Markdown tratado (frontmatter + corpo) das URLs da execução que já têm um."""
        treated: Dict[str, str] = {}

        for items in news_links.values():
            for item in items:
                url = item["url"] if isinstance(item, dict) else item
                record = self._storage.get_treated_news(url)

                if record is not None:
                    treated[url] = record.content

        return treated

    @staticmethod
    def _run_result(record: PipelineProcRecord) -> Optional[Dict[str, Any]]:
        """Resultado no formato de `PipelineRunResponse`, ou None sem desfecho renderizável."""
        if record.status not in _RENDERABLE_RESULT_STATUSES or not record.result:
            return None

        return {
            "pipeline_id": record.proc_id,
            "status": record.status,
            "stages_executed": record.result.get("stages_executed", []),
            "stage_results": record.result.get("stage_results", {}),
            "error_message": record.result.get("error_message"),
            "pending_treatment_urls": record.result.get("pending_treatment_urls"),
        }

    def _has_granger_report(self, proc_id: str) -> bool:
        """Se a execução gerou relatório de Granger."""
        return self._storage.get_granger_results(proc_id) is not None
