"""Test pipeline stages."""

import pytest
from datetime import datetime

from backend.src.pipeline.pipeline_stage import PipelineStage, PipelineStageResult
from backend.src.pipeline.stages import (
    FeatureEngineeringStage,
    ConfoundingHandlerStage,
    NewsTreatmentStage,
    DataCollectionStage,
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
            "verificar_conformidade",
        ]


class _NoPricesSource:
    """DataSource falso com uma única cotação por ticker (alvo e índice são obrigatórios)."""

    def get_stock_prices(self, ticker, date_range):
        from backend.src.domain.models import StockPrice

        return [StockPrice(ticker, datetime(2026, 1, 2), 10.0, 10.0, 10.0, 10.0, 100)]


def _treated_markdown(date_line):
    """Markdown tratado com frontmatter; `date_line` vazio omite o campo `date`."""
    lines = ["---", "title: Título", "subtitle: Sub", "url: https://g1/x"]
    if date_line:
        lines.append(f"date: {date_line}")
    lines += ["---", "Corpo da notícia."]
    return chr(10).join(lines)


def _collect(markdown, news_date):
    stage = DataCollectionStage(_NoPricesSource(), ["BBAS3.SA"])
    entry = {
        "url": "https://g1/x", "site": "G1", "markdown": markdown,
        "success": True, "treated": True, "news_date": news_date,
    }
    result = stage.execute({
        "date_range": {"start_date": datetime(2026, 1, 1), "end_date": datetime(2026, 12, 31)},
        "news_markdowns": [entry],
    })
    assert result.status == "SUCCESS"
    return result.data["news_items"]


class TestDataCollectionPublishedDate:
    """Data de publicação: frontmatter prevalece; `news_date` é fallback (Iteração 5)."""

    def test_frontmatter_date_is_used(self):
        items = _collect(_treated_markdown("10-06-2026"), "2026-06-10")

        assert [n.published_date for n in items] == [datetime(2026, 6, 10)]

    def test_news_date_is_fallback_when_frontmatter_has_no_date(self):
        items = _collect(_treated_markdown(""), "2026-11-03")

        assert [n.published_date for n in items] == [datetime(2026, 11, 3)]

    def test_news_date_is_fallback_when_frontmatter_date_is_invalid(self):
        items = _collect(_treated_markdown("não-é-data"), "2026-11-03")

        assert [n.published_date for n in items] == [datetime(2026, 11, 3)]

    def test_divergent_dates_use_frontmatter_and_log_warning(self, caplog):
        with caplog.at_level("WARNING"):
            items = _collect(_treated_markdown("10-06-2026"), "2026-11-03")

        assert [n.published_date for n in items] == [datetime(2026, 6, 10)]
        warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any(
            "https://g1/x" in w and "2026-06-10" in w and "2026-11-03" in w
            for w in warnings
        )

    def test_matching_dates_do_not_warn(self, caplog):
        with caplog.at_level("WARNING"):
            _collect(_treated_markdown("03-11-2026"), "2026-11-03")

        assert not [r for r in caplog.records if r.levelname == "WARNING"]

    def test_news_without_any_date_is_discarded(self):
        assert _collect(_treated_markdown(""), None) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
