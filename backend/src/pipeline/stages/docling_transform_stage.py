"""Docling Transform Stage - converte links de notícias em Markdown (etapa 0)."""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.models import ProcNewsRecord


class DoclingTransformStage(PipelineStage):
    """Converte links de notícias em Markdown via Docling (etapa 0)."""

    def __init__(self, converter, proc_news_repo=None):
        """Initialize with a Docling converter wrapper and a proc-news repository."""
        super().__init__("docling_transform")
        self.converter = converter            # DoclingConverterAdapter
        self.repo = proc_news_repo            # acesso à tabela PIPELINE_PROC_NEWS

    def substages(self) -> List[str]:
        """Subetapas em ordem (Seção 3 do spec)."""
        return ["validar_links", "converter_markdown", "registrar_proc_news"]

    def validate(self) -> bool:
        """Validate converter availability (Rule 2)."""
        return self.converter is not None

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Convert news links into Markdown (Rule 1: delegate)."""
        start_time = datetime.now()

        try:
            self._report_substage(on_substage, "validar_links")
            links = self._extract_links(input_data)

            self._report_substage(on_substage, "converter_markdown")
            markdowns = self._convert_batch(links)

            self._report_substage(on_substage, "registrar_proc_news")
            self._register_results(markdowns, input_data.get("pipeline_id"))

            output_data = self._create_output_data(markdowns)

            return self._create_success_result(
                start_time,
                datetime.now(),
                output_data,
            )

        except Exception as e:
            return self._create_failure_result(
                start_time,
                datetime.now(),
                str(e),
            )

    def _extract_links(self, input_data: Dict[str, Any]) -> List[str]:
        """Accept list[str] or a JSON string/object containing links (Rule 1)."""
        raw = input_data.get("news_links")

        if raw is None:
            return []

        if isinstance(raw, str):
            return self._parse_links_json(raw)

        if isinstance(raw, list):
            return [link for link in raw if isinstance(link, str) and link.strip()]

        return []

    def _parse_links_json(self, raw: str) -> List[str]:
        """Parse a JSON payload that may contain a list or a {'links': [...]} dict."""
        stripped = raw.strip()

        if not stripped:
            return []

        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [stripped]

        if isinstance(parsed, list):
            return [link for link in parsed if isinstance(link, str)]

        if isinstance(parsed, dict):
            links = parsed.get("links", [])
            return [link for link in links if isinstance(link, str)]

        return []

    def _convert_batch(self, links: List[str]) -> List[Dict[str, Any]]:
        """Convert each link into Markdown, ignoring non-textual media (Rule 1)."""
        results = []

        for url in links:
            results.append(self._convert_single(url))

        return results

    def _convert_single(self, url: str) -> Dict[str, Any]:
        """Convert one link, capturing success/failure per item (Rule 1)."""
        site = self.converter.site_name(url)

        try:
            markdown = self.converter.to_markdown(url)
            return {
                "url": url,
                "site": site,
                "markdown": markdown,
                "success": True,
            }

        except Exception as e:
            return {
                "url": url,
                "site": site,
                "markdown": "",
                "success": False,
                "error": str(e),
            }

    def _register_results(
        self,
        markdowns: List[Dict[str, Any]],
        pipeline_id: Optional[str],
    ) -> None:
        """Persist a PIPELINE_PROC_NEWS row per link, tagged with the run uuid (Rule 1)."""
        if not self.repo:
            return

        for entry in markdowns:
            record = ProcNewsRecord(
                url=entry["url"],
                proc_ts=datetime.now(),
                site_name=entry["site"],
                proc_success=entry["success"],
                proc_id=pipeline_id,
            )
            self.repo.save_proc_news(record)

    def _create_output_data(self, markdowns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create output data for next stage (Rule 1)."""
        return {
            "news_markdowns": markdowns,
            "docling_timestamp": datetime.now().isoformat(),
        }
