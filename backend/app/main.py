"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import Config, get_logger
from app.api.routes import pipeline_router, health_router

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    Config.ensure_directories()
    
    app = FastAPI(
        title=Config.APP_NAME,
        version=Config.APP_VERSION,
        description="Data Pipeline API for stock market analysis",
    )
    
    _setup_cors(app)
    _register_routes(app)
    
    logger.info(f"FastAPI app initialized: {Config.APP_NAME} v{Config.APP_VERSION}")
    
    return app


def _setup_cors(app: FastAPI):
    """Configure CORS middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _register_routes(app: FastAPI):
    """Register API routers."""
    app.include_router(health_router)
    app.include_router(pipeline_router, prefix=Config.API_PREFIX)
    
    logger.info("Routes registered")


# Create app instance
app = create_app()
