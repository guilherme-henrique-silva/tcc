"""Pipeline module - Orchestration of data processing stages."""

from .pipeline import DataPipeline, PipelineResult, StageName
from .dependency_container import DependencyContainer
from .pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    SubStageTag,
    ProgressCallback,
)
from .stages import (
    DoclingTransformStage,
    DataCollectionStage,
    FeatureEngineeringStage,
    ConfoundingHandlerStage,
    ModelingPreparationStage,
)

__all__ = [
    "DataPipeline",
    "PipelineResult",
    "StageName",
    "DependencyContainer",
    "PipelineStage",
    "PipelineStageResult",
    "SubStageTag",
    "ProgressCallback",
    "DoclingTransformStage",
    "DataCollectionStage",
    "FeatureEngineeringStage",
    "ConfoundingHandlerStage",
    "ModelingPreparationStage",
]
