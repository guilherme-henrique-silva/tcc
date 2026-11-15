"""Modeling Preparation Stage — análise exploratória, separada do teste de Granger."""

from typing import Dict, Any, List, Optional

from datetime import datetime

import pandas as pd

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.services.modeling_preparation_service import ModelingPreparationService
from app.core.logger import get_logger

logger = get_logger(__name__)


class ModelingPreparationStage(PipelineStage):
    """Stage for preparing exploratory datasets from the ``analysis_dataset``.

    Os artefatos (não supervisionado, supervisionado e *walk-forward*) são exploratórios e
    ficam **fora do teste** de Granger. Opcionalmente reporta o Granger fora da amostra.
    """

    def __init__(self, classification_mode: bool = False):
        """Initialize modeling preparation service."""
        super().__init__("modeling_preparation")
        self.service = ModelingPreparationService()
        self.classification_mode = classification_mode

    def substages(self) -> List[str]:
        """Subetapas em ordem."""
        return ["dataset_nao_supervisionado", "dataset_supervisionado", "walk_forward"]

    def execute(
        self,
        input_data: Dict[str, Any],
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineStageResult:
        """Prepare data for modeling."""
        start_time = datetime.now()

        try:
            dataset = self._analysis_frame(input_data)
            unsupervised_dataset = supervised_dataset = None

            self._report_substage(on_substage, "dataset_nao_supervisionado")
            if dataset is not None:
                unsupervised_dataset, supervised_dataset = (
                    self.service.prepare_from_analysis_dataset(dataset, self.classification_mode)
                )

            self._report_substage(on_substage, "dataset_supervisionado")
            supervised_dataset = self._non_empty(supervised_dataset)

            self._report_substage(on_substage, "walk_forward")
            walk_forward_splits = self._prepare_walk_forward_splits(supervised_dataset)
            out_of_sample = self._out_of_sample_granger(dataset, input_data)

            output_data = self._create_output_data(
                unsupervised_dataset,
                supervised_dataset,
                walk_forward_splits,
                out_of_sample,
            )

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

    def validate(self) -> bool:
        """Validate service availability."""
        return self.service is not None

    @staticmethod
    def _analysis_frame(input_data: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """``analysis_dataset`` (records) como DataFrame; None quando ausente."""
        records = input_data.get("analysis_dataset")
        if not records:
            logger.warning("analysis_dataset ausente: preparação exploratória sem dados")
            return None

        return pd.DataFrame(records)

    @staticmethod
    def _non_empty(dataset):
        """None quando o dataset supervisionado está vazio (sem linhas utilizáveis)."""
        if dataset is None or len(dataset.X) == 0:
            return None

        return dataset

    def _prepare_walk_forward_splits(self, supervised_dataset):
        """Prepare walk-forward validation splits."""
        if supervised_dataset is None:
            return []

        try:
            splits = self.service.apply_walk_forward_split(supervised_dataset)
            return splits or []

        except Exception as exc:  # noqa: BLE001 — artefato exploratório não derruba a pipeline
            logger.warning("Falha ao gerar os splits walk-forward: %s", exc)
            return []

    def _out_of_sample_granger(
        self,
        dataset: Optional[pd.DataFrame],
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Granger fora da amostra (opcional): RMSE restrito × irrestrito em janelas móveis."""
        if dataset is None:
            return {"status": "not_available", "reason": "analysis_dataset ausente"}

        report = input_data.get("granger_report") or {}
        lag = int((report.get("lag_selection") or {}).get("chosen") or 1)

        try:
            return self.service.out_of_sample_granger(dataset, lag=lag)

        except Exception as exc:  # noqa: BLE001 — complemento opcional
            logger.warning("Granger fora da amostra indisponível: %s", exc)
            return {"status": "error", "reason": str(exc)}

    def _create_output_data(
        self,
        unsupervised_dataset,
        supervised_dataset,
        walk_forward_splits: list,
        out_of_sample_granger: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create output data."""
        return {
            "unsupervised_dataset": unsupervised_dataset,
            "supervised_dataset": supervised_dataset,
            "walk_forward_splits": walk_forward_splits,
            "out_of_sample_granger": out_of_sample_granger,
            "preparation_timestamp": datetime.now().isoformat(),
            "classification_mode": self.classification_mode,
        }
