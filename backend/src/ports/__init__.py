"""Ports module initialization."""

from .data_source import DataSourcePort, StoragePort, NewsProcessorPort

__all__ = [
    "DataSourcePort",
    "StoragePort",
    "NewsProcessorPort",
]
