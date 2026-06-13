"""Health check routes."""

from fastapi import APIRouter

from app.core import Config
from app.api.schemas import HealthCheckResponse, DbHealthResponse
from app.core.logger import get_logger
from src.adapters.storage import SQLiteStorage

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


@router.get("/health/db", response_model=DbHealthResponse)
async def health_check_db():
    """Check database connectivity, reporting the failure reason (Seção 7 do spec)."""
    reason = SQLiteStorage(Config.DATABASE_URL).check_connection()

    if reason:
        logger.error(f"Database health check failed: {reason}")
        return DbHealthResponse(status="error", reason=reason)

    return DbHealthResponse(status="ok")


@router.get("/ready")
async def readiness_check():
    """Kubernetes readiness check."""
    return {"status": "ready"}
