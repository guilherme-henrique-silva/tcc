"""Pydantic schemas for API request/response validation (DTOs)."""

from datetime import date, datetime
from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field


# Request schemas
class DateRangeRequest(BaseModel):
    """DTO for date range input."""
    start_date: date = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: date = Field(..., description="End date (YYYY-MM-DD)")


ALL_STAGE_NAMES = [
    "docling_transform",
    "news_treatment",
    "data_collection",
    "feature_engineering",
    "confounding_handling",
    "modeling_preparation",
]


class PipelineExecuteRequest(BaseModel):
    """DTO for pipeline execution request."""
    news_file_path: Optional[str] = Field(
        None,
        description="Path to CSV file with news data"
    )
    date_range: DateRangeRequest = Field(..., description="Date range for analysis")
    enabled_stages: Optional[List[str]] = Field(
        None,
        description="Stages to run (feature toggle). None = all stages enabled."
    )
    news_links: Optional[List[str]] = Field(
        None,
        description="News links for the Docling transform stage (manual collection)."
    )
    use_llm_treatment: bool = Field(
        False,
        description="Auto-treat pending news via LLM in the treatment stage."
    )
    treatment_model_path: Optional[str] = Field(
        None,
        description="Selected local model path for LLM treatment (LLM_BACKEND=local)."
    )
    discarded_news_urls: Optional[List[str]] = Field(
        None,
        description="URLs to exclude from treatment (user chose to discard and advance)."
    )

    class Config:
        schema_extra = {
            "example": {
                "news_file_path": "/data/news_2025.csv",
                "date_range": {
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                },
                "enabled_stages": ALL_STAGE_NAMES,
                "news_links": ["https://g1.globo.com/economia/noticia.ghtml"],
                "use_llm_treatment": False,
            }
        }


class StageResultDTO(BaseModel):
    """DTO for a single stage outcome."""
    stage_name: str
    status: Literal["SUCCESS", "FAILED", "SKIPPED", "BLOCKED"]
    error_message: Optional[str] = None


class PipelineRunResponse(BaseModel):
    """DTO for a synchronous pipeline run result."""
    pipeline_id: str
    status: Literal["SUCCESS", "FAILED", "BLOCKED"]
    stages_executed: List[str]
    stage_results: Dict[str, StageResultDTO]
    error_message: Optional[str] = None
    pending_treatment_urls: Optional[List[str]] = None


class ProcNewsDTO(BaseModel):
    """DTO for a PIPELINE_PROC_NEWS record."""
    URL: str
    PROC_ID: Optional[str] = None
    PROC_TS: str
    NM_SITE: Optional[str] = None
    PROC_SUCCESS: bool


class ConvertLinkRequest(BaseModel):
    """DTO for converting a single news link into Markdown on demand."""
    url: str = Field(..., description="News link to convert via Docling")


class ConvertLinkResponse(BaseModel):
    """DTO for the Markdown produced from a single link."""
    url: str
    site: str
    markdown: str
    success: bool
    error: Optional[str] = None


class TreatNewsRequest(BaseModel):
    """DTO for treating one news Markdown via LLM."""
    markdown: str = Field(..., description="Raw Markdown produced by Docling")
    model_path: Optional[str] = Field(
        None,
        description="Selected local model path (only used when LLM_BACKEND=local)."
    )


class TreatNewsResponse(BaseModel):
    """DTO for the treated news Markdown (frontmatter + cleaned body)."""
    treated_markdown: str


class TreatedNewsSaveRequest(BaseModel):
    """DTO for persisting a treated news document from the UI."""
    url: str = Field(..., description="News link (record key)")
    treated_markdown: str = Field(..., description="Treated Markdown with frontmatter")
    proc_id: Optional[str] = Field(None, description="Associated execution uuid, if any")


class TreatedNewsDTO(BaseModel):
    """DTO for a PIPELINE_TREATED_NEWS record."""
    URL: str
    PROC_ID: Optional[str] = None
    TITLE: str
    SUBTITLE: str
    NEWS_DATE: str
    CONTENT: str


class LlmModelDTO(BaseModel):
    """DTO for one entry of the LLM_MODELS catalog with on-disk status."""
    name: str
    path: str
    vram: str
    best_use: str
    status: Literal["ready", "download", "downloading"]


class DownloadModelRequest(BaseModel):
    """DTO for triggering an on-demand model download."""
    model_path: str = Field(..., description="Catalog path of the model to download")


class DownloadModelResponse(BaseModel):
    """DTO for the result of starting a model download."""
    model_path: str
    status: Literal["ready", "downloading", "download"]


class CheckpointResumeRequest(BaseModel):
    """DTO for resuming from checkpoint."""
    checkpoint_id: str = Field(..., description="Checkpoint ID to resume from")


# Response schemas
class CheckpointDTO(BaseModel):
    """DTO for checkpoint information."""
    checkpoint_id: str
    stage: str
    timestamp: str
    status: Literal["SUCCESS", "FAILED"]
    next_stage: Optional[str] = None
    data_summary: Dict


class PipelineStatusResponse(BaseModel):
    """DTO for pipeline status response."""
    job_id: str
    status: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"]
    current_stage: str
    progress_percent: int
    error: Optional[str] = None
    error_details: Optional[Dict] = None
    last_checkpoint: Optional[CheckpointDTO] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "job_20260609_143022_abc123",
                "status": "RUNNING",
                "current_stage": "features",
                "progress_percent": 60,
                "error": None,
                "last_checkpoint": {
                    "checkpoint_id": "checkpoint_20260609_143022_validate",
                    "stage": "validate",
                    "timestamp": "2026-06-09T14:30:22Z",
                    "status": "SUCCESS",
                    "next_stage": "features",
                    "data_summary": {"rows": 252},
                },
            }
        }


class FeaturesExportDTO(BaseModel):
    """DTO for feature export response."""
    stage: str
    n_samples: int
    n_features: int
    feature_names: List[str]
    data: List[Dict]
    
    class Config:
        schema_extra = {
            "example": {
                "stage": "features",
                "n_samples": 252,
                "n_features": 45,
                "feature_names": [
                    "date",
                    "ticker",
                    "daily_return_pct",
                    "volatility_20d",
                ],
                "data": [
                    {
                        "date": "2025-01-02",
                        "ticker": "BBAS3.SA",
                        "daily_return_pct": 0.5,
                        "volatility_20d": 1.2,
                    }
                ],
            }
        }


class ValidationReportDTO(BaseModel):
    """DTO for data validation report."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    summary: Dict = Field(default_factory=dict)
    
    class Config:
        schema_extra = {
            "example": {
                "valid": True,
                "errors": [],
                "warnings": ["Low correlation between some competitors"],
                "summary": {
                    "n_records": 252,
                    "date_range": "2025-01-01 to 2025-12-31",
                    "missing_values": 0,
                },
            }
        }


class HealthCheckResponse(BaseModel):
    """DTO for health check response."""
    status: str
    version: str
    uptime_seconds: float
    checkpoints_count: int


class DbHealthResponse(BaseModel):
    """DTO for database connectivity check."""
    status: Literal["ok", "error"]
    reason: Optional[str] = None
