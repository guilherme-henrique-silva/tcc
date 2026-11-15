"""Docling Transform Stage - converte links de notícias em Markdown (etapa 0)."""

from typing import Dict, Any, List, Optional
from datetime import date, datetime, time

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.models import ProcNewsRecord
from src.domain.value_objects import NewsLinksByDate


class DoclingTransformStage(PipelineStage):
    """Converte links de notícias em Markdown via Docling (etapa 0)."""

    def __init__(self, converter, proc_news_repo=None):
        """Initialize with a Docling converter wrapper and a proc-news repository."""
        super().__init__("docling_transform")
        self.converter = converter            # DoclingConverterAdapter
        self.repo = proc_news_repo            # acesso à tabela PIPELINE_PROC_NEWS

    def substages(self) -> List[str]:
        """Subetapas em ordem."""
        return ["validar_links", "converter_markdown", "registrar_proc_news"]

    def validate(self) -> bool:
        """Validate converter availability."""
        return self.converter is not None

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Convert news links into Markdown."""
        start_time = datetime.now()

        try:
            self._report_substage(on_substage, "validar_links")
            links = self._extract_dated_links(input_data)

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

    def _extract_dated_links(self, input_data: Dict[str, Any]) -> NewsLinksByDate:
        """Read `input_data["news_links"]` as an object mapping publication date -> links.

        Valid example (dict or the same content as a JSON string):

            {"news_links": {
                "2026-11-03": ["https://g1.globo.com/economia/noticia/a.ghtml",
                               "https://www.infomoney.com.br/mercados/b/"],
                "2026-11-04": ["https://g1.globo.com/economia/noticia/c.ghtml"],
            }}

        Edge cases: None/ausente/string em branco/`{}` -> coleção vazia (etapa SUCCESS
        sem itens). Qualquer estrutura inválida levanta `ValueError`, que `execute`
        converte em FAILED: lista plana (formato legado), `{"links": [...]}`, string que
        não é JSON, data malformada ou futura, valor que não é lista, item vazio ou
        não-string e a mesma URL em duas datas.
        """
        return NewsLinksByDate.from_raw(input_data.get("news_links"))

    def _convert_batch(self, links: NewsLinksByDate) -> List[Dict[str, Any]]:
        """Convert each link into Markdown, ignoring non-textual media."""
        results = []

        for url, news_date, news_time in links.items():
            results.append(self._convert_single(url, news_date, news_time))

        return results

    def _convert_single(
        self,
        url: str,
        news_date: date,
        news_time: Optional[time] = None,
    ) -> Dict[str, Any]:
        """Convert one link, capturing success/failure per item.

        ``news_time`` ("HH:MM", Brasília) é propagado como veio do JSON de entrada;
        ``None`` quando o horário não foi informado.
        """
        site = self.converter.site_name(url)
        published = news_date.isoformat()
        published_time = news_time.strftime("%H:%M") if news_time else None

        try:
            markdown = self.converter.to_markdown(url)
            return {
                "url": url,
                "site": site,
                "markdown": markdown,
                "success": True,
                "news_date": published,
                "news_time": published_time,
            }

        except Exception as e:
            return {
                "url": url,
                "site": site,
                "markdown": "",
                "success": False,
                "error": str(e),
                "news_date": published,
                "news_time": published_time,
            }

    def _register_results(
        self,
        markdowns: List[Dict[str, Any]],
        pipeline_id: Optional[str],
    ) -> None:
        """Persist a PIPELINE_PROC_NEWS row per link, tagged with the run uuid."""
        if not self.repo:
            return

        for entry in markdowns:
            record = ProcNewsRecord(
                url=entry["url"],
                proc_ts=datetime.now(),
                site_name=entry["site"],
                proc_success=entry["success"],
                proc_id=pipeline_id,
                news_date=date.fromisoformat(entry["news_date"]),
                news_time=(
                    time.fromisoformat(entry["news_time"])
                    if entry.get("news_time")
                    else None
                ),
            )
            self.repo.save_proc_news(record)

    def _create_output_data(self, markdowns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create output data for next stage."""
        return {
            "news_markdowns": markdowns,
            "docling_timestamp": datetime.now().isoformat(),
        }
