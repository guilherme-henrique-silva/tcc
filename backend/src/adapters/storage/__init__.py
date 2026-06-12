"""Storage adapters."""

from .sqlite_storage import SQLiteStorage
from .csv_storage import CsvStorage

__all__ = ["SQLiteStorage", "CsvStorage"]
