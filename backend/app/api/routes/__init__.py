"""Routes module initialization."""

from .pipeline_routes import router as pipeline_router
from .health_routes import router as health_router

__all__ = [
    "pipeline_router",
    "health_router",
]
