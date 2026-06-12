"""Pipeline control routes."""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List, Set
import uuid
from datetime import datetime

from app.api.schemas import (
    PipelineExecuteRequest,
    CheckpointResumeRequest,
    PipelineStatusResponse,
    PipelineRunResponse,
    StageResultDTO,
    ProcNewsDTO,
    CheckpointDTO,
)
from app.core.logger import get_logger
from app.core.exceptions import PipelineException
from app.core.config import Config
from src.pipeline import DataPipeline, DependencyContainer, StageName
from persistence.checkpoint_manager import CheckpointManager

logger = get_logger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# In-memory job store (replace with database in production)
JOBS_STORE = {}

# Initialize pipeline with dependencies
_config = Config()
_checkpoint_manager = CheckpointManager(_config.CHECKPOINT_DIR)
_container = DependencyContainer(_config)
_pipeline = DataPipeline(_config, _checkpoint_manager, _container)


@router.post("/execute", response_model=PipelineRunResponse)
async def execute_pipeline(request: PipelineExecuteRequest):
    """
    Execute the data pipeline synchronously honoring the feature toggle (Seção 2).

    Returns per-stage SUCCESS/SKIPPED/FAILED statuses.
    """
    return_early_if_invalid = _validate_request(request)
    if return_early_if_invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=return_early_if_invalid,
        )

    pipeline = DataPipeline(_config, _checkpoint_manager, _container)
    enabled_stages = _parse_enabled_stages(request.enabled_stages)

    logger.info(f"Pipeline run started: {pipeline.pipeline_id}")

    result = pipeline.execute(
        request.date_range.start_date,
        request.date_range.end_date,
        enabled_stages=enabled_stages,
        news_links=request.news_links,
        news_file_path=request.news_file_path,
    )

    return _to_run_response(result)


@router.get("/proc_news", response_model=Optional[ProcNewsDTO])
async def get_proc_news(url: str):
    """Return the PIPELINE_PROC_NEWS record for a URL, if present (Seção 8.5)."""
    record = _container.get_storage().get_proc_news(url)

    if not record:
        return None

    return ProcNewsDTO(**record.to_dict())


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(job_id: str):
    """Get current pipeline execution status."""
    job_data = _get_job_or_404(job_id)
    
    return PipelineStatusResponse(
        job_id=job_id,
        status=job_data["status"],
        current_stage=job_data["current_stage"],
        progress_percent=job_data["progress_percent"],
        error=job_data.get("error"),
        error_details=job_data.get("error_details"),
        last_checkpoint=job_data.get("last_checkpoint"),
        start_time=job_data.get("start_time"),
        end_time=job_data.get("end_time"),
    )


@router.post("/resume", response_model=PipelineStatusResponse)
async def resume_from_checkpoint(request: CheckpointResumeRequest):
    """Resume pipeline from specific checkpoint."""
    checkpoint_id = request.checkpoint_id
    logger.info(f"Resuming pipeline from checkpoint: {checkpoint_id}")
    
    new_job_id = _create_job_id()
    job_data = _initialize_job_from_checkpoint(new_job_id, checkpoint_id)
    JOBS_STORE[new_job_id] = job_data
    
    return PipelineStatusResponse(
        job_id=new_job_id,
        status="PENDING",
        current_stage="resuming",
        progress_percent=0,
    )


@router.post("/cancel")
async def cancel_pipeline(job_id: str):
    """Cancel running pipeline."""
    job_data = _get_job_or_404(job_id)
    
    job_data["status"] = "CANCELLED"
    logger.info(f"Pipeline job cancelled: {job_id}")
    
    return {
        "message": "Pipeline cancelled",
        "job_id": job_id,
        "stage": job_data["current_stage"],
    }


@router.get("/checkpoints")
async def list_checkpoints():
    """List available checkpoints for recovery."""
    # TODO: Implement checkpoint listing
    return {"checkpoints": []}


# Helper functions (Rule 7: Keep methods small)

def _create_job_id() -> str:
    """Generate unique job ID."""
    return f"job_{uuid.uuid4().hex[:8]}"


def _validate_request(request: PipelineExecuteRequest) -> Optional[str]:
    """
    Validate pipeline request.

    Returns error message if invalid, None if valid.
    """
    if request.date_range.start_date > request.date_range.end_date:
        return "start_date must be before end_date"

    return None  # Valid


def _parse_enabled_stages(
    enabled_stages: Optional[List[str]],
) -> Optional[Set[StageName]]:
    """Convert the request stage names into a StageName set (None = all)."""
    if enabled_stages is None:
        return None

    parsed = set()
    for name in enabled_stages:
        try:
            parsed.add(StageName(name))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown stage: {name}",
            )

    return parsed


def _to_run_response(result) -> PipelineRunResponse:
    """Map a PipelineResult into the API response DTO (Rule 1)."""
    stage_results = {
        name: StageResultDTO(
            stage_name=stage_result.stage_name,
            status=stage_result.status,
            error_message=stage_result.error_message,
        )
        for name, stage_result in result.stage_results.items()
    }

    return PipelineRunResponse(
        pipeline_id=result.pipeline_id,
        status=result.status,
        stages_executed=result.stages_executed,
        stage_results=stage_results,
        error_message=result.error_message,
    )


def _initialize_job(job_id: str, request: PipelineExecuteRequest) -> dict:
    """Initialize job data structure."""
    return {
        "job_id": job_id,
        "status": "PENDING",
        "current_stage": "initialization",
        "progress_percent": 0,
        "request": request.dict(),
        "error": None,
        "error_details": None,
        "last_checkpoint": None,
        "start_time": None,
        "end_time": None,
    }


def _initialize_job_from_checkpoint(job_id: str, checkpoint_id: str) -> dict:
    """Initialize job from checkpoint data."""
    return {
        "job_id": job_id,
        "status": "PENDING",
        "current_stage": "resuming",
        "progress_percent": 0,
        "checkpoint_id": checkpoint_id,
        "error": None,
        "error_details": None,
        "last_checkpoint": None,
        "start_time": None,
        "end_time": None,
    }


def _get_job_or_404(job_id: str) -> dict:
    """Get job or raise 404."""
    if job_id not in JOBS_STORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )
    
    return JOBS_STORE[job_id]
