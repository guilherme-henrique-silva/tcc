"""Exception types for the application."""

from enum import Enum
from typing import Optional, Dict


class PipelineErrorCode(Enum):
    """Error codes for pipeline exceptions."""
    INVALID_INPUT = "INVALID_INPUT"
    STAGE_FAILED = "STAGE_FAILED"
    CHECKPOINT_NOT_FOUND = "CHECKPOINT_NOT_FOUND"
    DATA_VALIDATION_ERROR = "DATA_VALIDATION_ERROR"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PROCESSING_ERROR = "PROCESSING_ERROR"


class PipelineException(Exception):
    """Base exception for pipeline errors."""
    
    def __init__(
        self,
        error_code: PipelineErrorCode,
        stage: str,
        message: str,
        details: Optional[Dict] = None,
    ):
        """
        Initialize pipeline exception.
        
        Args:
            error_code: Error code enum
            stage: Pipeline stage where error occurred
            message: Human-readable error message
            details: Additional error details
        """
        self.error_code = error_code
        self.stage = stage
        self.message = message
        self.details = details or {}
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict:
        """Convert exception to dictionary for API response."""
        return {
            "error_code": self.error_code.value,
            "stage": self.stage,
            "message": self.message,
            "details": self.details,
        }


class InvalidInputException(PipelineException):
    """Raised when input validation fails."""
    
    def __init__(self, stage: str, message: str, details: Optional[Dict] = None):
        super().__init__(PipelineErrorCode.INVALID_INPUT, stage, message, details)


class StageFailedException(PipelineException):
    """Raised when a pipeline stage fails."""
    
    def __init__(self, stage: str, message: str, details: Optional[Dict] = None):
        super().__init__(PipelineErrorCode.STAGE_FAILED, stage, message, details)


class CheckpointNotFoundException(PipelineException):
    """Raised when checkpoint is not found."""
    
    def __init__(self, checkpoint_id: str, details: Optional[Dict] = None):
        super().__init__(
            PipelineErrorCode.CHECKPOINT_NOT_FOUND,
            "checkpoint_recovery",
            f"Checkpoint not found: {checkpoint_id}",
            details,
        )


class DataValidationException(PipelineException):
    """Raised when data validation fails."""
    
    def __init__(self, stage: str, message: str, details: Optional[Dict] = None):
        super().__init__(PipelineErrorCode.DATA_VALIDATION_ERROR, stage, message, details)
