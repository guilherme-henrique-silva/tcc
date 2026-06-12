"""Logging configuration."""

import logging
import sys
from app.core.config import Config

# Configure logging format
LOG_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
)

# Create logger
logger = logging.getLogger("app")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(LOG_FORMAT)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(Config.LOG_LEVEL)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(f"app.{name}")
