"""CSV Storage Adapter."""

from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from pathlib import Path

from src.ports.data_source import StoragePort
from src.domain.models import ProcNewsRecord, PipelineProcRecord, TreatedNewsRecord


class CsvStorage(StoragePort):
    """Adapter for exporting features to CSV files."""
    
    def __init__(self, base_path: str = "./data"):
        """Initialize with base directory for CSV files."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_features(self, features: pd.DataFrame, dataset_id: str) -> None:
        """Save features to CSV file."""
        try:
            output_path = self._get_features_path(dataset_id)
            features.to_csv(output_path, index=False)
        
        except (OSError, IOError):
            pass
    
    def load_features(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Load features from CSV file."""
        try:
            csv_path = self._get_features_path(dataset_id)
            
            if not csv_path.exists():
                return None
            
            return pd.read_csv(csv_path)
        
        except (OSError, IOError, pd.errors.ParserError):
            return None
    
    def save_validation_results(self, results: Dict) -> None:
        """Save validation results to CSV."""
        try:
            df = pd.DataFrame([results])
            output_path = self.base_path / "validation_results.csv"
            
            if output_path.exists():
                df.to_csv(output_path, mode="a", header=False, index=False)
            else:
                df.to_csv(output_path, index=False)
        
        except (OSError, IOError):
            pass
    
    def save_granger_test_results(self, results: Dict) -> None:
        """Save Granger test results to CSV."""
        try:
            df = pd.DataFrame([results])
            output_path = self.base_path / "granger_results.csv"
            
            if output_path.exists():
                df.to_csv(output_path, mode="a", header=False, index=False)
            else:
                df.to_csv(output_path, index=False)
        
        except (OSError, IOError):
            pass
    
    # --- Rastreabilidade de execução -----------------------------
    # O adapter CSV exporta apenas features; os registros de execução vivem no
    # SQLiteStorage. Implementações no-op mantêm o contrato do StoragePort.

    def save_proc_news(self, record: ProcNewsRecord) -> None:
        """Not persisted by the CSV adapter (feature export only)."""
        return None

    def get_proc_news(self, url: str) -> Optional[ProcNewsRecord]:
        """Not persisted by the CSV adapter (feature export only)."""
        return None

    def save_pipeline_proc(self, record: PipelineProcRecord) -> None:
        """Not persisted by the CSV adapter (feature export only)."""
        return None

    def finish_pipeline_proc(self, proc_id: str, end_ts: datetime) -> None:
        """Not persisted by the CSV adapter (feature export only)."""
        return None

    def save_treated_news(self, record: TreatedNewsRecord) -> None:
        """Not persisted by the CSV adapter (feature export only)."""
        return None

    def get_treated_news(self, url: str) -> Optional[TreatedNewsRecord]:
        """Not persisted by the CSV adapter (feature export only)."""
        return None

    def list_treated_news(self, proc_id: str) -> List[TreatedNewsRecord]:
        """Not persisted by the CSV adapter (feature export only)."""
        return []

    def _get_features_path(self, dataset_id: str) -> Path:
        """Get CSV path for features."""
        safe_id = dataset_id.replace("/", "_")
        return self.base_path / f"features_{safe_id}.csv"
