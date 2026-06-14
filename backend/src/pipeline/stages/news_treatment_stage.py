"""News Treatment Stage - trata as notícias (manual/LLM) após o Docling."""

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.ports.llm import LlmPort
from src.domain.models import TreatedNewsRecord
from src.adapters.llm import PROMPT_TRATAMENTO_NOTICIAS

# Factory que entrega um LlmPort para o modelo selecionado por execução.
LlmProvider = Callable[[Optional[str]], LlmPort]


class NewsTreatmentStage(PipelineStage):
    """Garante que cada notícia tenha um documento tratado, reusando o que a UI já tratou.

    Modelo "página dedicada + stage consumidora" (decisão de projeto): o tratamento
    interativo (manual/LLM, validação lado a lado) acontece na página de Tratamento;
    aqui a etapa consome os documentos tratados persistidos e, quando o modo LLM está
    ativo, trata automaticamente os registros ainda pendentes.
    """

    def __init__(self, storage, llm_provider: LlmProvider):
        """Initialize with the storage port and an LLM provider factory."""
        super().__init__("news_treatment")
        self.storage = storage
        self._llm_provider = llm_provider

    def substages(self) -> List[str]:
        """Subetapas em ordem."""
        return ["selecionar_registros", "tratar_llm", "persistir_tratados"]

    def validate(self) -> bool:
        """Validate storage availability."""
        return self.storage is not None

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Ensure a treated document exists per news item."""
        start_time = datetime.now()

        try:
            self._report_substage(on_substage, "selecionar_registros")
            entries = self._select_entries(input_data)
            proc_id = input_data.get("pipeline_id")
            use_llm = bool(input_data.get("use_llm_treatment", False))
            model_path = input_data.get("treatment_model_path")

            self._report_substage(on_substage, "tratar_llm")
            treated = [
                self._treat_entry(entry, proc_id, use_llm, model_path)
                for entry in entries
            ]

            self._report_substage(on_substage, "persistir_tratados")
            output_data = self._create_output_data(treated)

            return self._create_success_result(start_time, datetime.now(), output_data)

        except Exception as e:
            return self._create_failure_result(start_time, datetime.now(), str(e))

    def _select_entries(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Keep only successfully converted markdowns from Docling."""
        markdowns = input_data.get("news_markdowns") or []
        return [entry for entry in markdowns if entry.get("success")]

    def _treat_entry(
        self,
        entry: Dict[str, Any],
        proc_id: Optional[str],
        use_llm: bool,
        model_path: Optional[str],
    ) -> Dict[str, Any]:
        """Resolve the treated markdown for one entry, reusing or generating it."""
        url = entry.get("url")
        existing = self.storage.get_treated_news(url) if url else None

        if existing:
            return self._reuse_existing(entry, existing, proc_id)

        if use_llm:
            return self._treat_with_llm(entry, proc_id, model_path)

        # Modo manual sem tratamento persistido: segue com o markdown bruto.
        return self._passthrough(entry)

    def _reuse_existing(
        self,
        entry: Dict[str, Any],
        existing: TreatedNewsRecord,
        proc_id: Optional[str],
    ) -> Dict[str, Any]:
        """Reuse a document treated earlier, re-stamping the current run."""
        if proc_id and existing.proc_id != proc_id:
            self.storage.save_treated_news(
                TreatedNewsRecord(
                    url=existing.url,
                    title=existing.title,
                    subtitle=existing.subtitle,
                    date=existing.date,
                    content=existing.content,
                    proc_id=proc_id,
                )
            )

        return self._as_output(entry, existing.content, treated=True)

    def _treat_with_llm(
        self,
        entry: Dict[str, Any],
        proc_id: Optional[str],
        model_path: Optional[str],
    ) -> Dict[str, Any]:
        """Treat a pending entry via the LLM and persist the result."""
        llm = self._llm_provider(model_path)
        treated_markdown = llm.treat_news(
            entry.get("markdown", ""),
            prompt=PROMPT_TRATAMENTO_NOTICIAS,
        )

        record = TreatedNewsRecord.from_treated_markdown(
            url=entry.get("url"),
            treated_markdown=treated_markdown,
            proc_id=proc_id,
        )
        self.storage.save_treated_news(record)

        return self._as_output(entry, treated_markdown, treated=True)

    def _passthrough(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Keep the raw markdown when no treatment is available."""
        return self._as_output(entry, entry.get("markdown", ""), treated=False)

    def _as_output(
        self,
        entry: Dict[str, Any],
        markdown: str,
        *,
        treated: bool,
    ) -> Dict[str, Any]:
        """Build the news entry consumed downstream by DataCollection."""
        return {
            "url": entry.get("url"),
            "site": entry.get("site"),
            "markdown": markdown,
            "success": True,
            "treated": treated,
        }

    def _create_output_data(self, treated: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create output data for next stage, replacing news_markdowns."""
        return {
            "news_markdowns": treated,
            "treatment_timestamp": datetime.now().isoformat(),
        }
