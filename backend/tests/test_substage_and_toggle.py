"""Tests for SubStageTag and per-stage skip behavior (Seções 2 e 3 do spec)."""

import pytest

from backend.src.pipeline.pipeline_stage import (
    PipelineStage,
    PipelineStageResult,
    SubStageTag,
)


class _ThreeSubstageStage(PipelineStage):
    """Stage with three substages emitting tags on execute."""

    def __init__(self):
        super().__init__("demo_stage")
        self.emitted = []

    def substages(self):
        return ["a", "b", "c"]

    def validate(self):
        return True

    def execute(self, input_data, on_substage=None):
        from datetime import datetime

        for name in self.substages():
            self._report_substage(on_substage, name)
        return self._create_success_result(datetime.now(), datetime.now(), {})


def test_substage_tag_order_ratio_and_label():
    """order_ratio = order/total and label is human readable (Seção 3)."""
    tag = SubStageTag("data_collection", "coletar_precos", 1, 2)

    assert tag.order_ratio == 0.5
    assert tag.label == "data_collection · coletar_precos (1/2)"


def test_report_substage_emits_tags_in_order():
    """Each substage emits a SubStageTag with coherent order/total (Seção 3)."""
    stage = _ThreeSubstageStage()
    tags = []

    stage.execute({}, on_substage=tags.append)

    assert [t.substage_name for t in tags] == ["a", "b", "c"]
    assert [t.order for t in tags] == [1, 2, 3]
    assert all(t.total == 3 for t in tags)
    assert tags[-1].order_ratio == 1.0


def test_create_skipped_result_status():
    """Disabled stages produce a SKIPPED result (Seção 2)."""
    stage = _ThreeSubstageStage()

    result = stage.create_skipped_result()

    assert isinstance(result, PipelineStageResult)
    assert result.status == "SKIPPED"
    assert result.stage_name == "demo_stage"
    assert result.data is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
