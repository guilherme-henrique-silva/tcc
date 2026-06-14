"""Integration test for pipeline orchestration."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from backend.src.pipeline import DataPipeline, DependencyContainer
from backend.app.core.config import Config


class TestDataPipeline:
    """Test DataPipeline orchestrator (Rule 7: test class)."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.config = Config()
        self.pipeline = DataPipeline(config=self.config)
    
    def test_pipeline_initialization(self):
        """Test pipeline initializes with all stages."""
        assert self.pipeline is not None
        # 6 stages: docling_transform + news_treatment + data_collection
        # + feature_engineering + confounding_handling + modeling_preparation.
        assert len(self.pipeline._stages) == 6
        assert self.pipeline.pipeline_id is not None

    def test_pipeline_stage_order_includes_treatment(self):
        """News treatment runs between Docling and data collection (Requisito 9)."""
        names = [stage.stage_name for stage in self.pipeline._stages]

        assert names == [
            "docling_transform",
            "news_treatment",
            "data_collection",
            "feature_engineering",
            "confounding_handling",
            "modeling_preparation",
        ]
    
    def test_pipeline_validate_input_valid(self):
        """Test input validation with valid data."""
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 12, 31)
        
        is_valid = self.pipeline.validate_input(start_date, end_date)
        
        assert is_valid is True
    
    def test_pipeline_validate_input_invalid_missing_start(self):
        """Test input validation with missing start date."""
        end_date = datetime(2025, 12, 31)
        
        is_valid = self.pipeline.validate_input(None, end_date)
        
        assert is_valid is False
    
    def test_pipeline_validate_input_invalid_missing_end(self):
        """Test input validation with missing end date."""
        start_date = datetime(2025, 1, 1)
        
        is_valid = self.pipeline.validate_input(start_date, None)
        
        assert is_valid is False
    
    def test_pipeline_validate_input_invalid_reversed_dates(self):
        """Test input validation with reversed dates."""
        start_date = datetime(2025, 12, 31)
        end_date = datetime(2025, 1, 1)
        
        is_valid = self.pipeline.validate_input(start_date, end_date)
        
        assert is_valid is False
    
    def test_dependency_container_initialization(self):
        """Test dependency container initializes correctly."""
        container = DependencyContainer(config=self.config)
        
        assert container is not None
        assert container.config is not None
    
    def test_dependency_container_data_source_singleton(self):
        """Test dependency container returns singleton for data source."""
        container = DependencyContainer(config=self.config)
        
        source1 = container.get_data_source()
        source2 = container.get_data_source()
        
        assert source1 is source2
    
    def test_dependency_container_storage_singleton(self):
        """Test dependency container returns singleton for storage."""
        container = DependencyContainer(config=self.config)
        
        storage1 = container.get_storage()
        storage2 = container.get_storage()
        
        assert storage1 is storage2
    
    def test_dependency_container_sentiment_analyzer(self):
        """Test dependency container provides sentiment analyzer."""
        container = DependencyContainer(config=self.config)
        
        analyzer = container.get_sentiment_analyzer()
        
        assert analyzer is not None
    
    def test_dependency_container_entity_extractor(self):
        """Test dependency container provides entity extractor."""
        container = DependencyContainer(config=self.config)
        
        extractor = container.get_entity_extractor()
        
        assert extractor is not None
    
    def test_dependency_container_tfidf_processor(self):
        """Test dependency container provides TF-IDF processor."""
        container = DependencyContainer(config=self.config)
        
        processor = container.get_tfidf_processor()
        
        assert processor is not None
    
    def test_dependency_container_reset_singletons(self):
        """Test dependency container can reset singleton instances."""
        container = DependencyContainer(config=self.config)

        source1 = container.get_data_source()
        container.reset_singletons()
        source2 = container.get_data_source()

        assert source1 is not source2

    def test_dependency_container_provides_llm(self):
        """Container provides an LlmPort adapter for news treatment (Requisitos 10/11)."""
        container = DependencyContainer(config=self.config)

        llm = container.get_llm()

        assert llm is not None
        assert hasattr(llm, "treat_news")


class TestDateRangeSplit:
    """DateRange.split(): chunking de período sem sobreposição."""

    def test_period_shorter_than_max_returns_self(self):
        from datetime import date
        from backend.src.domain.value_objects.date_range import DateRange

        dr = DateRange(date(2025, 1, 1), date(2025, 6, 30))
        chunks = dr.split(max_days=365)

        assert chunks == [dr]

    def test_period_exactly_max_days_returns_self(self):
        from datetime import date
        from backend.src.domain.value_objects.date_range import DateRange

        start = date(2025, 1, 1)
        end = date(2025, 12, 31)
        dr = DateRange(start, end)
        chunks = dr.split(max_days=365)

        assert chunks == [dr]

    def test_period_one_day_over_splits_into_two(self):
        from datetime import date
        from backend.src.domain.value_objects.date_range import DateRange

        start = date(2024, 1, 1)
        end = date(2025, 1, 1)  # 366 dias (ano bissexto 2024)
        dr = DateRange(start, end)
        chunks = dr.split(max_days=365)

        assert len(chunks) == 2

    def test_chunks_are_non_overlapping(self):
        from datetime import date, timedelta
        from backend.src.domain.value_objects.date_range import DateRange

        dr = DateRange(date(2023, 1, 1), date(2025, 12, 31))
        chunks = dr.split(max_days=365)

        for i in range(len(chunks) - 1):
            assert chunks[i].end_date + timedelta(days=1) == chunks[i + 1].start_date

    def test_chunks_cover_full_interval(self):
        from datetime import date
        from backend.src.domain.value_objects.date_range import DateRange

        dr = DateRange(date(2022, 3, 15), date(2025, 9, 20))
        chunks = dr.split(max_days=365)

        assert chunks[0].start_date == dr.start_date
        assert chunks[-1].end_date == dr.end_date

    def test_no_chunk_exceeds_max_days(self):
        from datetime import date
        from backend.src.domain.value_objects.date_range import DateRange

        dr = DateRange(date(2020, 1, 1), date(2025, 12, 31))
        max_days = 365
        chunks = dr.split(max_days=max_days)

        for chunk in chunks:
            assert chunk.days_count <= max_days

    def test_single_day_range_returns_self(self):
        from datetime import date
        from backend.src.domain.value_objects.date_range import DateRange

        dr = DateRange(date(2025, 6, 1), date(2025, 6, 1))
        chunks = dr.split(max_days=365)

        assert chunks == [dr]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
