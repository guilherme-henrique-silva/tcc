"""Testes da NewsTreatmentStage: modos manual/LLM, frontmatter e seleção (Requisito 13)."""

import pytest

from backend.src.pipeline.stages import NewsTreatmentStage
from backend.src.domain.models import TreatedNewsRecord


class _FakeStorage:
    """Storage em memória que registra os documentos tratados persistidos."""

    def __init__(self, existing=None):
        self.saved = {}
        self._existing = existing or {}

    def get_treated_news(self, url):
        return self._existing.get(url)

    def save_treated_news(self, record):
        self.saved[record.url] = record


class _FakeLlm:
    """LlmPort falso que conta chamadas e devolve um markdown tratado determinístico."""

    def __init__(self):
        self.calls = 0

    def treat_news(self, markdown, *, prompt):
        self.calls += 1
        return f"---\ntitle: T\nsubtitle: \nurl: u\ndate: 01-01-2026\n---\nlimpo:{markdown}"


def _input(use_llm, model=None):
    return {
        "news_markdowns": [
            {"url": "u1", "site": "G1", "markdown": "bruto", "success": True},
            {"url": "u2", "site": "G1", "markdown": "x", "success": False},
        ],
        "pipeline_id": "run-1",
        "use_llm_treatment": use_llm,
        "treatment_model_path": model,
    }


def test_selects_only_successful_entries():
    stage = NewsTreatmentStage(_FakeStorage(), lambda mp: _FakeLlm())
    result = stage.execute(_input(False))

    assert result.status == "SUCCESS"
    assert len(result.data["news_markdowns"]) == 1  # entrada com success=False é descartada


def test_llm_mode_treats_and_persists_with_proc_id():
    llm = _FakeLlm()
    storage = _FakeStorage()
    stage = NewsTreatmentStage(storage, lambda mp: llm)

    result = stage.execute(_input(True))
    entry = result.data["news_markdowns"][0]

    assert entry["treated"] is True
    assert entry["markdown"].startswith("---")
    assert llm.calls == 1
    assert storage.saved["u1"].proc_id == "run-1"
    assert storage.saved["u1"].title == "T"  # frontmatter parseado na persistência


def test_manual_mode_passthrough_when_no_treated_doc():
    llm = _FakeLlm()
    storage = _FakeStorage()
    stage = NewsTreatmentStage(storage, lambda mp: llm)

    result = stage.execute(_input(False))
    entry = result.data["news_markdowns"][0]

    assert entry["treated"] is False
    assert entry["markdown"] == "bruto"
    assert llm.calls == 0
    assert storage.saved == {}


def test_reuses_existing_treated_doc_and_restamps_run():
    existing = {
        "u1": TreatedNewsRecord(
            url="u1", title="T", subtitle="", date="", content="TRATADO", proc_id="old",
        )
    }
    llm = _FakeLlm()
    storage = _FakeStorage(existing)
    stage = NewsTreatmentStage(storage, lambda mp: llm)

    result = stage.execute(_input(True))
    entry = result.data["news_markdowns"][0]

    assert entry["markdown"] == "TRATADO"
    assert entry["treated"] is True
    assert llm.calls == 0  # reutiliza, não re-trata
    assert storage.saved["u1"].proc_id == "run-1"  # re-carimba a execução atual


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
