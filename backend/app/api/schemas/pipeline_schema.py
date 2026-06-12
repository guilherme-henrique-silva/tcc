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
            }
        }


class StageResultDTO(BaseModel):
    """DTO for a single stage outcome."""
    stage_name: str
    status: Literal["SUCCESS", "FAILED", "SKIPPED"]
    error_message: Optional[str] = None


class PipelineRunResponse(BaseModel):
    """DTO for a synchronous pipeline run result (Seção 2 do spec)."""
    pipeline_id: str
    status: Literal["SUCCESS", "FAILED"]
    stages_executed: List[str]
    stage_results: Dict[str, StageResultDTO]
    error_message: Optional[str] = None


class ProcNewsDTO(BaseModel):
    """DTO for a PIPELINE_PROC_NEWS record (Seção 8 do spec)."""
    URL: str
    TS_PROC: str
    NM_SITE: Optional[str] = None
    PROC_SUCCESS: bool


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
