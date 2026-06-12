"""Health check routes."""

from fastapi import APIRouter
from datetime import datetime

from app.core import Config
from app.api.schemas import HealthCheckResponse
from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(
        status="ok",
        version=Config.APP_VERSION,
        uptime_seconds=0.0,  # TODO: Calculate actual uptime
        checkpoints_count=0,  # TODO: Count actual checkpoints
    )


@router.get("/ready")
async def readiness_check():
    """Kubernetes readiness check."""
    return {"status": "ready"}
