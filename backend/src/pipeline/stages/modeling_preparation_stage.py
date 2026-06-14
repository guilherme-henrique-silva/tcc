"""Modeling Preparation Stage."""

from typing import Dict, Any, List, Optional

from datetime import datetime

from src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    ProgressCallback,
)
from src.domain.services.modeling_preparation_service import ModelingPreparationService


class ModelingPreparationStage(PipelineStage):
    """Stage for preparing data for modeling (Rule 7: small entity)."""

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
        """Prepare data for modeling (Rule 1: delegate)."""
        start_time = datetime.now()

        try:
            self._report_substage(on_substage, "dataset_nao_supervisionado")
            unsupervised_dataset = self._prepare_unsupervised(input_data)

            self._report_substage(on_substage, "dataset_supervisionado")
            supervised_dataset = self._prepare_supervised(input_data)

            self._report_substage(on_substage, "walk_forward")
            walk_forward_splits = self._prepare_walk_forward_splits(supervised_dataset)
            
            output_data = self._create_output_data(
                unsupervised_dataset,
                supervised_dataset,
                walk_forward_splits,
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
        """Validate service availability (Rule 2)."""
        return self.service is not None
    
    def _prepare_unsupervised(self, input_data: Dict[str, Any]):
        """Prepare unsupervised learning dataset (Rule 1)."""
        try:
            # TODO: Extract stock and news features from input_data
            # service.prepare_unsupervised_data(stock_features, news_features)
            return None
        
        except Exception:
            return None
    
    def _prepare_supervised(self, input_data: Dict[str, Any]):
        """Prepare supervised learning dataset (Rule 1)."""
        try:
            # TODO: Extract all features and target from input_data
            # service.prepare_supervised_data(...)
            return None
        
        except Exception:
            return None
    
    def _prepare_walk_forward_splits(self, supervised_dataset):
        """Prepare walk-forward validation splits (Rule 1)."""
        if not supervised_dataset:
            return []
        
        try:
            splits = self.service.apply_walk_forward_split(supervised_dataset)
            return splits or []
        
        except Exception:
            return []
    
    def _create_output_data(
        self,
        unsupervised_dataset,
        supervised_dataset,
        walk_forward_splits: list,
    ) -> Dict[str, Any]:
        """Create output data (Rule 1)."""
        return {
            "unsupervised_dataset": unsupervised_dataset,
            "supervised_dataset": supervised_dataset,
            "walk_forward_splits": walk_forward_splits,
            "preparation_timestamp": datetime.now().isoformat(),
            "classification_mode": self.classification_mode,
        }
