"""Test pipeline stages."""

import pytest
from datetime import datetime

from backend.src.pipeline.pipeline_stage import PipelineStage, PipelineStageResult
from backend.src.pipeline.stages import (
    FeatureEngineeringStage,
    ConfoundingHandlerStage,
    NewsTreatmentStage,
)


class MockStage(PipelineStage):
    """Mock stage for testing."""
    
    def execute(self, input_data, on_substage=None):
        """Mock execution."""
        start_time = datetime.now()
        return self._create_success_result(
            start_time,
            datetime.now(),
            {"test": "data"},
        )
    
    def validate(self):
        """Mock validation."""
        return True


class TestPipelineStages:
    """Test pipeline stage base class and implementations."""
    
    def test_pipeline_stage_success_result(self):
        """Test creating success result."""
        stage = MockStage("test_stage")
        result = stage.execute({})
        
        assert result.status == "SUCCESS"
        assert result.stage_name == "test_stage"
        assert result.data == {"test": "data"}
        assert result.error_message is None
    
    def test_feature_engineering_stage_initialization(self):
        """Test feature engineering stage initializes."""
        stage = FeatureEngineeringStage()
        
        assert stage is not None
        assert stage.stage_name == "feature_engineering"
    
    def test_feature_engineering_stage_validation(self):
        """Test feature engineering stage validation."""
        stage = FeatureEngineeringStage()
        
        is_valid = stage.validate()
        
        assert is_valid is True
    
    def test_confounding_handler_stage_initialization(self):
        """Test confounding handler stage initializes."""
        stage = ConfoundingHandlerStage()
        
        assert stage is not None
        assert stage.stage_name == "confounding_handling"
    
    def test_confounding_handler_stage_validation(self):
        """Test confounding handler stage validation."""
        stage = ConfoundingHandlerStage()

        is_valid = stage.validate()

        assert is_valid is True

    def test_news_treatment_stage_initialization(self):
        """News treatment stage initializes with its name and validates (Requisito 9)."""
        stage = NewsTreatmentStage(storage=object(), llm_provider=lambda mp: None)

        assert stage.stage_name == "news_treatment"
        assert stage.validate() is True
        assert stage.substages() == [
            "selecionar_registros",
            "tratar_llm",
            "persistir_tratados",
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
