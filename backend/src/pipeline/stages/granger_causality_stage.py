"""Granger Causality Stage — teste de Granger em VAR sobre o dataset de análise."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.services.granger_causality_service import (
    GrangerCausalityService,
    GrangerModelError,
    InsufficientDataError,
)
from app.core.config import Config
from app.core.logger import get_logger

logger = get_logger(__name__)

MISSING_DATASET_MESSAGE = "dataset de análise ausente — habilite confounding_handling"


class GrangerCausalityStage(PipelineStage):
    """Roda o teste de Granger, persiste o relatório e exporta os artefatos de reprodução.

    Saídas persistidas (RF-11): linha em ``granger_results`` com o PROC_ID da execução e,
    em ``DATA_DIR/granger/``, ``analysis_dataset_<proc_id>.csv`` e
    ``granger_report_<proc_id>.json``.
    """

    def __init__(
        self,
        storage=None,
        service: Optional[GrangerCausalityService] = None,
        data_dir: Optional[str] = None,
    ):
        """Initialize with the storage port, the Granger service and the export directory."""
        super().__init__("granger_causality")
        self.storage = storage
        self.data_dir = Path(data_dir or Config.DATA_DIR)
        self.service = service or GrangerCausalityService(
            max_lag=Config.GRANGER_MAX_LAG,
            ic=Config.GRANGER_IC,
            alpha=Config.GRANGER_ALPHA,
            multitest=Config.GRANGER_MULTITEST,
            news_spec=Config.GRANGER_NEWS_SPEC,
        )

    def substages(self) -> List[str]:
        """Subetapas em ordem."""
        return ["estacionariedade", "selecao_defasagens", "testes_granger", "diagnosticos"]

    def validate(self) -> bool:
        """Validate service availability."""
        return self.service is not None

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Run the Granger test over ``analysis_dataset`` and persist the report."""
        start_time = datetime.now()
        records = input_data.get("analysis_dataset")

        if not records:
            return self._create_failure_result(
                start_time, datetime.now(), MISSING_DATASET_MESSAGE
            )

        try:
            dataset = pd.DataFrame(records)
            report = self.service.run(
                dataset,
                alignment_audit=input_data.get("alignment_audit"),
                warnings=input_data.get("analysis_warnings"),
                on_phase=lambda phase: self._report_substage(on_substage, phase),
            )
            proc_id = input_data.get("pipeline_id")
            payload = {**report.to_dict(), "proc_id": proc_id}

            self._persist(payload, dataset, proc_id)

            return self._create_success_result(
                start_time,
                datetime.now(),
                {"granger_report": payload, "granger_timestamp": datetime.now().isoformat()},
            )

        except (InsufficientDataError, GrangerModelError, OSError) as exc:
            logger.error("Etapa granger_causality falhou: %s", exc)
            return self._create_failure_result(start_time, datetime.now(), str(exc))

        except Exception as exc:  # noqa: BLE001 — qualquer outra falha também vira FAILED
            logger.exception("Erro inesperado na etapa granger_causality")
            return self._create_failure_result(start_time, datetime.now(), str(exc))

    def _persist(
        self,
        payload: Dict[str, Any],
        dataset: pd.DataFrame,
        proc_id: Optional[str],
    ) -> None:
        """Grava o relatório em ``granger_results`` e exporta CSV/JSON (erros não são silenciados)."""
        if self.storage is not None:
            self.storage.save_granger_test_results(payload, proc_id=proc_id)

        folder = self.data_dir / "granger"
        folder.mkdir(parents=True, exist_ok=True)
        suffix = proc_id or "sem_proc_id"

        dataset.to_csv(folder / f"analysis_dataset_{suffix}.csv", index=False)
        with open(folder / f"granger_report_{suffix}.json", "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
