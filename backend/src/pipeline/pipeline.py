"""Main Pipeline Orchestrator - Coordinates all stages and services."""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import uuid

from src.pipeline.pipeline_stage import (
    PipelineStageResult,
    ProgressCallback,
)
from src.pipeline.stages import (
    DoclingTransformStage,
    NewsTreatmentStage,
    DataCollectionStage,
    FeatureEngineeringStage,
    ConfoundingHandlerStage,
    GrangerCausalityStage,
    ModelingPreparationStage,
)
from src.pipeline.dependency_container import DependencyContainer
from src.domain.models import PipelineProcRecord
from src.domain.models.pipeline_proc import STATUS_FAILED, STATUS_RUNNING
from persistence.checkpoint_manager import CheckpointManager
from app.core.config import Config
from app.core.logger import get_logger


class StageName(str, Enum):
    """Identificadores das etapas habilitáveis da pipeline."""

    DOCLING_TRANSFORM = "docling_transform"
    NEWS_TREATMENT = "news_treatment"
    DATA_COLLECTION = "data_collection"
    FEATURE_ENGINEERING = "feature_engineering"
    CONFOUNDING_HANDLING = "confounding_handling"
    GRANGER_CAUSALITY = "granger_causality"
    MODELING_PREPARATION = "modeling_preparation"


@dataclass(frozen=True)
class PipelineResult:
    """Encapsulates pipeline execution result."""

    pipeline_id: str
    status: str  # "SUCCESS", "FAILED", "BLOCKED"
    start_time: datetime
    end_time: datetime
    stages_executed: List[str]
    stage_results: Dict[str, PipelineStageResult]
    error_message: Optional[str] = None
    checkpoint_id: Optional[str] = None
    pending_treatment_urls: Optional[List[str]] = None

    def to_summary(self) -> Dict[str, Any]:
        """Resultado em JSON puro — é o que `PIPELINE_PROC_ID.RESULT` guarda para recarga."""
        return {
            "stages_executed": list(self.stages_executed),
            "stage_results": {
                name: {
                    "stage_name": stage_result.stage_name,
                    "status": stage_result.status,
                    "error_message": stage_result.error_message,
                }
                for name, stage_result in self.stage_results.items()
            },
            "error_message": self.error_message,
            "pending_treatment_urls": self.pending_treatment_urls,
        }


class DataPipeline:
    """Main orchestrator for entire data processing pipeline."""

    def __init__(
        self,
        config: Config = None,
        checkpoint_manager: CheckpointManager = None,
        dependency_container: DependencyContainer = None,
    ):
        """Initialize pipeline with configuration and dependencies."""
        self.config = config or Config()
        self.checkpoint_manager = checkpoint_manager or self._create_checkpoint_manager()
        self.container = dependency_container or DependencyContainer(config)
        self.logger = get_logger(__name__)

        self.pipeline_id = str(uuid.uuid4())
        self._stages = self._initialize_stages()

    def execute(
        self,
        date_range_start,
        date_range_end,
        *,
        enabled_stages: Optional[Set[StageName]] = None,
        news_links: Optional[Dict[str, list]] = None,
        news_file_path: str = None,
        use_llm_treatment: bool = False,
        treatment_model_path: Optional[str] = None,
        discarded_news_urls: Optional[List[str]] = None,
        on_substage: Optional[ProgressCallback] = None,
    ) -> PipelineResult:
        """
        Execute the pipeline, honoring the per-stage feature toggle.

        Args:
            enabled_stages: set of StageName to run; None = run all stages.
            news_links: news links grouped by publication date (YYYY-MM-DD -> items)
                for the Docling transform stage; each item is a URL string or
                {"url": ..., "time": "HH:MM"} (Brasília).
            on_substage: optional callback fired for each SubStageTag.

        Returns PipelineResult with per-stage SUCCESS/SKIPPED/FAILED status.
        """
        overall_start = datetime.now()
        self._record_run_start(
            overall_start,
            date_range_start,
            date_range_end,
            self._request_snapshot(
                enabled_stages,
                news_links,
                use_llm_treatment,
                treatment_model_path,
                discarded_news_urls,
            ),
        )
        result: Optional[PipelineResult] = None

        try:
            input_data = self._create_initial_input(
                date_range_start,
                date_range_end,
                news_file_path,
                news_links,
                use_llm_treatment,
                treatment_model_path,
                discarded_news_urls,
            )

            result = self._run_stages(
                input_data, enabled_stages, on_substage, overall_start
            )
            return result

        finally:
            self._record_run_end(datetime.now(), result)

    def _run_stages(
        self,
        input_data: Dict[str, Any],
        enabled_stages: Optional[Set[StageName]],
        on_substage: Optional[ProgressCallback],
        overall_start: datetime,
    ) -> PipelineResult:
        """Run the stages in order, stopping at the first BLOCKED/FAILED one."""
        stage_results: Dict[str, PipelineStageResult] = {}
        stages_executed: List[str] = []

        for stage in self._stages:
            if self._is_stage_disabled(stage, enabled_stages):
                stage_results[stage.stage_name] = stage.create_skipped_result()
                stages_executed.append(stage.stage_name)
                self.logger.info(f"Stage {stage.stage_name} SKIPPED (feature toggle)")
                continue

            stage_result = self._execute_stage(stage, input_data, on_substage)

            stage_results[stage.stage_name] = stage_result
            stages_executed.append(stage.stage_name)

            if stage_result.status == "BLOCKED":
                pending_urls = (stage_result.data or {}).get(
                    "pending_treatment_urls", []
                )
                return self._create_blocked_result(
                    overall_start,
                    datetime.now(),
                    stages_executed,
                    stage_results,
                    pending_urls,
                )

            if stage_result.status == "FAILED":
                return self._create_failed_result(
                    overall_start,
                    datetime.now(),
                    stages_executed,
                    stage_results,
                    stage_result.error_message,
                )

            input_data = self._merge_stage_output(input_data, stage_result.data)

        return self._create_success_result(
            overall_start,
            datetime.now(),
            stages_executed,
            stage_results,
        )

    def resume_from_checkpoint(self, checkpoint_id: str) -> PipelineResult:
        """Resume pipeline from saved checkpoint."""
        try:
            checkpoint = self.checkpoint_manager.load_checkpoint(checkpoint_id)

            if not checkpoint:
                return self._create_checkpoint_not_found_result(checkpoint_id)

            # TODO: Continue from next stage
            return self._create_failed_result(
                datetime.now(),
                datetime.now(),
                [],
                {},
                "Resume functionality not yet implemented",
            )

        except Exception as e:
            return self._create_failed_result(
                datetime.now(),
                datetime.now(),
                [],
                {},
                f"Checkpoint error: {str(e)}",
            )

    def validate_input(
        self,
        date_range_start,
        date_range_end,
        news_file_path: str = None,
    ) -> bool:
        """Validate pipeline input parameters."""
        if not date_range_start:
            return False

        if not date_range_end:
            return False

        if date_range_start > date_range_end:
            return False

        return True

    def _record_run_start(
        self,
        start_time: datetime,
        date_range_start,
        date_range_end,
        request: Dict[str, Any],
    ) -> None:
        """Persist a PIPELINE_PROC_ID row with the run inputs, so it can be reloaded later."""
        record = PipelineProcRecord(
            proc_id=self.pipeline_id,
            proc_ts_start=start_time,
            proc_ts_end=None,
            status=STATUS_RUNNING,
            date_start=date_range_start,
            date_end=date_range_end,
            request=request,
        )
        self.container.get_storage().save_pipeline_proc(record)

    def _record_run_end(
        self,
        end_time: datetime,
        result: Optional[PipelineResult] = None,
    ) -> None:
        """Stamp the end, final status and result once the execution ends.

        ``result`` é None quando uma exceção inesperada escapou das etapas: a execução
        fica registrada como FAILED em vez de presa em RUNNING.
        """
        status = result.status if result else STATUS_FAILED
        summary = result.to_summary() if result else None

        self.container.get_storage().finish_pipeline_proc(
            self.pipeline_id, end_time, status=status, result=summary
        )

    def _request_snapshot(
        self,
        enabled_stages: Optional[Set[StageName]],
        news_links: Optional[Dict[str, list]],
        use_llm_treatment: bool,
        treatment_model_path: Optional[str],
        discarded_news_urls: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Entradas da execução em JSON puro (`PIPELINE_PROC_ID.REQUEST`)."""
        stages = (
            None
            if enabled_stages is None
            else sorted(self._stage_value(name) for name in enabled_stages)
        )
        return {
            "enabled_stages": stages,
            "news_links": news_links or {},
            "use_llm_treatment": use_llm_treatment,
            "treatment_model_path": treatment_model_path,
            "discarded_news_urls": discarded_news_urls or [],
        }

    def _initialize_stages(self) -> List:
        """Initialize all pipeline stages, Docling as stage 0 (ordem: docs/PIPELINE.md)."""
        data_source = self.container.get_data_source()
        tickers = self._parse_tickers()
        config = self.config

        stages = [
            DoclingTransformStage(
                self.container.get_docling_converter(),
                self.container.get_storage(),
            ),
            NewsTreatmentStage(
                self.container.get_storage(),
                self.container.get_llm,
            ),
            DataCollectionStage(
                data_source,
                tickers,
                self.container.get_sentiment_analyzer(),
                target_ticker=config.TARGET_TICKER,
                index_ticker=config.MARKET_INDEX_TICKER,
                commodity_tickers=config.COMMODITY_TICKERS,
            ),
            FeatureEngineeringStage(
                target_ticker=config.TARGET_TICKER,
                market_close_time=config.MARKET_CLOSE_TIME,
                peers_aggregation=config.PEERS_AGGREGATION,
                volatility_window=config.VOLATILITY_WINDOW,
                anomaly_std_threshold=config.ANOMALY_STD_THRESHOLD,
            ),
            ConfoundingHandlerStage(
                self.container.get_bcb_adapter(),
                config.COPOM_DECISION_DATES,
            ),
            GrangerCausalityStage(
                self.container.get_storage(),
                data_dir=config.DATA_DIR,
            ),
            ModelingPreparationStage(),
        ]

        return stages

    def _is_stage_disabled(
        self,
        stage,
        enabled_stages: Optional[Set[StageName]],
    ) -> bool:
        """Return True when the stage is not in the enabled set."""
        if enabled_stages is None:
            return False

        enabled_values = {self._stage_value(name) for name in enabled_stages}
        return stage.stage_name not in enabled_values

    def _stage_value(self, name) -> str:
        """Normalize a StageName/str to its string value."""
        if isinstance(name, StageName):
            return name.value

        return str(name)

    def _execute_stage(
        self,
        stage,
        input_data: Dict,
        on_substage: Optional[ProgressCallback],
    ) -> PipelineStageResult:
        """Execute single stage with error handling."""
        if not stage.validate():
            return PipelineStageResult(
                stage_name=stage.stage_name,
                status="FAILED",
                start_time=datetime.now(),
                end_time=datetime.now(),
                error_message=f"Stage validation failed: {stage.stage_name}",
            )

        result = stage.execute(input_data, on_substage)

        self.logger.info(
            f"Stage {stage.stage_name} completed with status {result.status}"
        )

        return result

    def _create_initial_input(
        self,
        date_range_start,
        date_range_end,
        news_file_path: str,
        news_links: Optional[Dict[str, list]],
        use_llm_treatment: bool = False,
        treatment_model_path: Optional[str] = None,
        discarded_news_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create initial input for first stage."""
        return {
            "date_range": {
                "start_date": date_range_start,
                "end_date": date_range_end,
            },
            "news_file_path": news_file_path,
            "news_links": news_links or {},
            "pipeline_id": self.pipeline_id,
            "use_llm_treatment": use_llm_treatment,
            "treatment_model_path": treatment_model_path,
            "discarded_news_urls": discarded_news_urls or [],
        }

    def _merge_stage_output(
        self,
        input_data: Dict,
        stage_output: Dict,
    ) -> Dict[str, Any]:
        """Merge stage output with input for next stage."""
        merged = input_data.copy()

        if stage_output:
            merged.update(stage_output)

        return merged

    def _parse_tickers(self) -> List[str]:
        """Parse tickers from configuration."""
        tickers = self.config.YFINANCE_TICKERS

        if not tickers:
            return []

        return [t.strip() for t in tickers]

    def _create_checkpoint_manager(self) -> CheckpointManager:
        """Create checkpoint manager instance."""
        checkpoint_dir = self.config.CHECKPOINT_DIR
        return CheckpointManager(checkpoint_dir)

    def _create_success_result(
        self,
        start_time: datetime,
        end_time: datetime,
        stages_executed: List[str],
        stage_results: Dict,
    ) -> PipelineResult:
        """Create successful pipeline result."""
        return PipelineResult(
            pipeline_id=self.pipeline_id,
            status="SUCCESS",
            start_time=start_time,
            end_time=end_time,
            stages_executed=stages_executed,
            stage_results=stage_results,
        )

    def _create_failed_result(
        self,
        start_time: datetime,
        end_time: datetime,
        stages_executed: List[str],
        stage_results: Dict,
        error_message: str,
    ) -> PipelineResult:
        """Create failed pipeline result."""
        return PipelineResult(
            pipeline_id=self.pipeline_id,
            status="FAILED",
            start_time=start_time,
            end_time=end_time,
            stages_executed=stages_executed,
            stage_results=stage_results,
            error_message=error_message,
        )

    def _create_blocked_result(
        self,
        start_time: datetime,
        end_time: datetime,
        stages_executed: List[str],
        stage_results: Dict,
        pending_treatment_urls: List[str],
    ) -> PipelineResult:
        """Create a BLOCKED pipeline result when treatment conformance gate fires."""
        return PipelineResult(
            pipeline_id=self.pipeline_id,
            status="BLOCKED",
            start_time=start_time,
            end_time=end_time,
            stages_executed=stages_executed,
            stage_results=stage_results,
            pending_treatment_urls=pending_treatment_urls,
        )

    def _create_checkpoint_not_found_result(self, checkpoint_id: str) -> PipelineResult:
        """Create result for missing checkpoint."""
        return self._create_failed_result(
            datetime.now(),
            datetime.now(),
            [],
            {},
            f"Checkpoint not found: {checkpoint_id}",
        )
