"""Pipeline control routes."""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List, Set
import threading
import uuid
from datetime import datetime

from app.api.schemas import (
    PipelineExecuteRequest,
    CheckpointResumeRequest,
    PipelineStatusResponse,
    PipelineRunResponse,
    StageResultDTO,
    ProcNewsDTO,
    ConvertLinkRequest,
    ConvertLinkResponse,
    TreatNewsRequest,
    TreatNewsResponse,
    TreatedNewsSaveRequest,
    TreatedNewsDTO,
    LlmModelDTO,
    DownloadModelRequest,
    DownloadModelResponse,
    CheckpointDTO,
)
from app.core.logger import get_logger
from app.core.exceptions import PipelineException
from app.core.config import Config
from src.domain.models import TreatedNewsRecord
from src.pipeline import DataPipeline, DependencyContainer, StageName
from persistence.checkpoint_manager import CheckpointManager

logger = get_logger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# In-memory job store (replace with database in production)
JOBS_STORE = {}

# Downloads de modelos em andamento — alimentam o status "🔁 baixando".
_DOWNLOADS_IN_PROGRESS: Set[str] = set()
_DOWNLOADS_LOCK = threading.Lock()

# Initialize pipeline with dependencies
_config = Config()
_checkpoint_manager = CheckpointManager(_config.CHECKPOINT_DIR)
_container = DependencyContainer(_config)
_pipeline = DataPipeline(_config, _checkpoint_manager, _container)


@router.post("/execute", response_model=PipelineRunResponse)
async def execute_pipeline(request: PipelineExecuteRequest):
    """Execute the data pipeline synchronously, retornando status por etapa."""
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
        use_llm_treatment=request.use_llm_treatment,
        treatment_model_path=request.treatment_model_path,
    )

    return _to_run_response(result)


@router.get("/proc_news", response_model=Optional[ProcNewsDTO])
async def get_proc_news(url: str):
    """Return the PIPELINE_PROC_NEWS record for a URL, if present."""
    record = _container.get_storage().get_proc_news(url)

    if not record:
        return None

    return ProcNewsDTO(**record.to_dict())


@router.post("/convert_link", response_model=ConvertLinkResponse)
async def convert_link(request: ConvertLinkRequest):
    """Converte um link de notícia em Markdown sob demanda para a UI de tratamento."""
    converter = _container.get_docling_converter()
    site = converter.site_name(request.url)

    try:
        markdown = converter.to_markdown(request.url)
        return ConvertLinkResponse(
            url=request.url, site=site, markdown=markdown, success=True,
        )

    except Exception as e:  # noqa: BLE001
        return ConvertLinkResponse(
            url=request.url, site=site, markdown="", success=False, error=str(e),
        )


@router.post("/treat_news", response_model=TreatNewsResponse)
async def treat_news(request: TreatNewsRequest):
    """Trata um Markdown de notícia via o adapter de LLM configurado."""
    from src.adapters.llm import PROMPT_TRATAMENTO_NOTICIAS

    llm = _container.get_llm(request.model_path)
    treated = llm.treat_news(request.markdown, prompt=PROMPT_TRATAMENTO_NOTICIAS)

    return TreatNewsResponse(treated_markdown=treated)


@router.post("/treated_news", response_model=TreatedNewsDTO)
async def save_treated_news(request: TreatedNewsSaveRequest):
    """Persiste um documento de notícia tratado/validado na UI."""
    record = TreatedNewsRecord.from_treated_markdown(
        url=request.url,
        treated_markdown=request.treated_markdown,
        proc_id=request.proc_id,
    )
    _container.get_storage().save_treated_news(record)

    return TreatedNewsDTO(**record.to_dict())


@router.get("/treated_news", response_model=Optional[TreatedNewsDTO])
async def get_treated_news(url: str):
    """Retorna o documento tratado de uma URL, se existir."""
    record = _container.get_storage().get_treated_news(url)

    if not record:
        return None

    return TreatedNewsDTO(**record.to_dict())


@router.get("/llm_models", response_model=List[LlmModelDTO])
async def list_llm_models():
    """Lista o catálogo de modelos locais com status em disco."""
    from src.adapters.llm.catalog import list_with_status

    enriched = list_with_status(
        _config.llm_models(),
        _config.LLM_MODELS_DIR,
        _downloads_in_progress(),
    )

    from src.adapters.llm.vram_tier import VramTier

    return [
        LlmModelDTO(
            name=str(model.get("name", "")),
            path=str(model.get("path", "")),
            vram=str(model.get("vram", "")),
            best_use=VramTier.from_vram_string(model.get("vram", "")).recommendation,
            status=model["status"],
        )
        for model in enriched
    ]


@router.post("/download_model", response_model=DownloadModelResponse)
async def download_model(request: DownloadModelRequest):
    """Inicia o download do modelo selecionado sob demanda, nunca antes do início."""
    download_status = _start_model_download(request.model_path)

    return DownloadModelResponse(
        model_path=request.model_path,
        status=download_status,
    )


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

def _downloads_in_progress() -> Set[str]:
    """Snapshot dos caminhos de modelos em download."""
    with _DOWNLOADS_LOCK:
        return set(_DOWNLOADS_IN_PROGRESS)


def _start_model_download(model_path: str) -> str:
    """Inicia o download em background do modelo selecionado, se necessário."""
    from src.adapters.llm.catalog import (
        find_by_path,
        repo_id_for,
        resolve_local_dir,
        disk_status,
        STATUS_READY,
    )

    entry = find_by_path(_config.llm_models(), model_path)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model not in catalog: {model_path}",
        )

    if disk_status(_config.LLM_MODELS_DIR, model_path, in_progress=()) == STATUS_READY:
        return "ready"  # já presente em disco — nunca rebaixa

    with _DOWNLOADS_LOCK:
        if model_path in _DOWNLOADS_IN_PROGRESS:
            return "downloading"
        _DOWNLOADS_IN_PROGRESS.add(model_path)

    repo_id = repo_id_for(entry)
    local_dir = str(resolve_local_dir(_config.LLM_MODELS_DIR, model_path))
    threading.Thread(
        target=_run_model_download,
        args=(model_path, repo_id, local_dir),
        daemon=True,
    ).start()

    return "downloading"


def _run_model_download(model_path: str, repo_id: str, local_dir: str) -> None:
    """Download the model snapshot in a daemon thread, clearing the flag at the end."""
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id=repo_id, local_dir=local_dir)

    except Exception as e:  # noqa: BLE001
        logger.error(f"Model download failed for {model_path}: {e}")

    finally:
        with _DOWNLOADS_LOCK:
            _DOWNLOADS_IN_PROGRESS.discard(model_path)


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
