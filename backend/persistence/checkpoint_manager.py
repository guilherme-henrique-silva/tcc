"""CheckpointManager - Handles pipeline state persistence and recovery."""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import pickle

from app.core.config import Config
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint."""
    checkpoint_id: str
    stage: str
    timestamp: str
    status: str  # SUCCESS, FAILED
    next_stage: Optional[str]
    data_summary: Dict
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


class CheckpointManager:
    """
    Manages pipeline checkpoints for recovery.
    
        """
    
    def __init__(self, checkpoint_dir: str = None):
        """Initialize checkpoint manager."""
        self.checkpoint_dir = checkpoint_dir or Config.CHECKPOINT_DIR
        Path(self.checkpoint_dir).mkdir(parents=True, exist_ok=True)
    
    def save_checkpoint(
        self,
        stage_name: str,
        data: Dict,
        status: str = "SUCCESS",
        next_stage: Optional[str] = None,
    ) -> str:
        """
        Save pipeline checkpoint.
        
        Args:
            stage_name: Current stage name
            data: State data to persist
            status: Checkpoint status (SUCCESS or FAILED)
            next_stage: Name of next stage
            
        Returns:
            Checkpoint ID
        """
        checkpoint_id = self._generate_checkpoint_id(stage_name)
        metadata = self._create_metadata(
            checkpoint_id=checkpoint_id,
            stage=stage_name,
            status=status,
            next_stage=next_stage,
            data_summary=self._summarize_data(data),
        )
        
        self._persist_checkpoint(checkpoint_id, metadata, data)
        logger.info(f"Saved checkpoint: {checkpoint_id} (stage: {stage_name})")
        
        return checkpoint_id
    
    def load_checkpoint(self, checkpoint_id: str) -> Dict:
        """
        Load checkpoint data.
        
        Args:
            checkpoint_id: Checkpoint identifier
            
        Returns:
            Checkpoint data
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")
        
        with open(checkpoint_path, "rb") as f:
            data = pickle.load(f)
        
        logger.info(f"Loaded checkpoint: {checkpoint_id}")
        return data
    
    def list_checkpoints(self) -> List[CheckpointMetadata]:
        """List all available checkpoints."""
        checkpoints = []
        
        for metadata_file in Path(self.checkpoint_dir).glob("*_metadata.json"):
            metadata = self._load_metadata(metadata_file)
            checkpoints.append(CheckpointMetadata(**metadata))
        
        return sorted(checkpoints, key=lambda x: x.timestamp, reverse=True)
    
    def get_most_recent_checkpoint(self) -> Optional[CheckpointMetadata]:
        """Get most recent checkpoint."""
        checkpoints = self.list_checkpoints()
        return checkpoints[0] if checkpoints else None
    
    def delete_checkpoint(self, checkpoint_id: str) -> None:
        """Delete checkpoint after successful completion."""
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        metadata_path = checkpoint_path.with_name(f"{checkpoint_id}_metadata.json")
        
        if checkpoint_path.exists():
            checkpoint_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()
        
        logger.info(f"Deleted checkpoint: {checkpoint_id}")
    
    def cleanup_old_checkpoints(self, keep_count: int = 5) -> None:
        """Remove old checkpoints, keeping most recent N."""
        checkpoints = self.list_checkpoints()
        
        for checkpoint in checkpoints[keep_count:]:
            self.delete_checkpoint(checkpoint.checkpoint_id)
    
    def _generate_checkpoint_id(self, stage_name: str) -> str:
        """Generate unique checkpoint ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"checkpoint_{timestamp}_{stage_name}"
    
    def _create_metadata(
        self,
        checkpoint_id: str,
        stage: str,
        status: str,
        next_stage: Optional[str],
        data_summary: Dict,
    ) -> CheckpointMetadata:
        """Create checkpoint metadata."""
        return CheckpointMetadata(
            checkpoint_id=checkpoint_id,
            stage=stage,
            timestamp=datetime.now().isoformat(),
            status=status,
            next_stage=next_stage,
            data_summary=data_summary,
        )
    
    def _summarize_data(self, data: Dict) -> Dict:
        """Summarize data for metadata."""
        summary = {}
        
        for key, value in data.items():
            summary[key] = self._get_value_summary(value)
        
        return summary
    
    def _get_value_summary(self, value) -> str:
        """Get summary of value."""
        if hasattr(value, "shape"):  # DataFrame
            return f"DataFrame {value.shape}"
        if isinstance(value, dict):
            return f"Dict with {len(value)} items"
        if isinstance(value, list):
            return f"List with {len(value)} items"
        return type(value).__name__
    
    def _persist_checkpoint(
        self,
        checkpoint_id: str,
        metadata: CheckpointMetadata,
        data: Dict,
    ) -> None:
        """Persist checkpoint to disk."""
        # Save metadata as JSON
        metadata_path = self._get_metadata_path(checkpoint_id)
        with open(metadata_path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)
        
        # Save data as pickle
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        with open(checkpoint_path, "wb") as f:
            pickle.dump(data, f)
    
    def _load_metadata(self, metadata_file: Path) -> Dict:
        """Load metadata from file."""
        with open(metadata_file, "r") as f:
            return json.load(f)
    
    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get checkpoint file path."""
        return Path(self.checkpoint_dir) / f"{checkpoint_id}.pkl"
    
    def _get_metadata_path(self, checkpoint_id: str) -> Path:
        """Get metadata file path."""
        return Path(self.checkpoint_dir) / f"{checkpoint_id}_metadata.json"
