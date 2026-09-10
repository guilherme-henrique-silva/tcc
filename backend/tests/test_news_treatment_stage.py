"""Testes da NewsTreatmentStage: breakpoint, descarte, reutilização, LLM e filtros."""

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
        return f"---\ntitle: T\nsubtitle: \nurl: u\ndate: 01-01-2026\ncategory: finanças\n---\nlimpo:{markdown}"


_TREATED_RECORD = TreatedNewsRecord(
    url="u1", title="T", subtitle="", date="01-01-2026",
    content="---\ntitle: T\nsubtitle: \nurl: u1\ndate: 01-01-2026\ncategory: finanças\n---\nTRATADO",
    category="finanças", proc_id="old",
)


def _input(use_llm, model=None, extra=None):
    data = {
        "news_markdowns": [
            {"url": "u1", "site": "G1", "markdown": "bruto", "success": True},
            {"url": "u2", "site": "G1", "markdown": "x", "success": False},
        ],
        "pipeline_id": "run-1",
        "use_llm_treatment": use_llm,
        "treatment_model_path": model,
    }
    if extra:
        data.update(extra)
    return data


# ---------------------------------------------------------------------------
# Filtro de entradas success=False
# ---------------------------------------------------------------------------

def test_only_successful_entries_reach_treatment():
    """Entradas com success=False não entram na fase de tratamento."""
    llm = _FakeLlm()
    stage = NewsTreatmentStage(_FakeStorage({"u1": _TREATED_RECORD}), lambda mp: llm)

    result = stage.execute(_input(False))

    assert result.status == "SUCCESS"
    assert len(result.data["news_markdowns"]) == 1
    assert result.data["news_markdowns"][0]["url"] == "u1"


# ---------------------------------------------------------------------------
# Breakpoint BLOCKED (R3)
# ---------------------------------------------------------------------------

def test_blocked_when_no_treated_doc_and_no_llm():
    """Sem doc tratado e sem LLM → BLOCKED com a URL pendente."""
    stage = NewsTreatmentStage(_FakeStorage(), lambda mp: _FakeLlm())

    result = stage.execute(_input(False))

    assert result.status == "BLOCKED"
    assert result.data["pending_treatment_urls"] == ["u1"]


def test_blocked_carries_all_pending_urls():
    """Múltiplos pendentes são listados no BLOCKED."""
    markdowns = [
        {"url": "a", "site": "G1", "markdown": "x", "success": True},
        {"url": "b", "site": "G1", "markdown": "y", "success": True},
    ]
    stage = NewsTreatmentStage(_FakeStorage(), lambda mp: _FakeLlm())

    result = stage.execute({"news_markdowns": markdowns, "use_llm_treatment": False, "pipeline_id": "p"})

    assert result.status == "BLOCKED"
    assert set(result.data["pending_treatment_urls"]) == {"a", "b"}


# ---------------------------------------------------------------------------
# Filtro de URLs descartadas (R3)
# ---------------------------------------------------------------------------

def test_discarded_urls_are_excluded_and_remaining_treated():
    """URLs em discarded_news_urls não entram no processamento; resto segue normal."""
    existing = {"u1": _TREATED_RECORD}
    stage = NewsTreatmentStage(_FakeStorage(existing), lambda mp: _FakeLlm())

    inp = _input(False, extra={
        "news_markdowns": [
            {"url": "u1", "site": "G1", "markdown": "bruto", "success": True},
            {"url": "u3", "site": "G1", "markdown": "bruto3", "success": True},
        ],
        "discarded_news_urls": ["u3"],
    })

    result = stage.execute(inp)

    assert result.status == "SUCCESS"
    urls_out = [e["url"] for e in result.data["news_markdowns"]]
    assert "u3" not in urls_out
    assert "u1" in urls_out


def test_discarding_all_pending_results_in_success_with_empty_output():
    """Se todos os pendentes são descartados, a saída é vazia mas status é SUCCESS."""
    stage = NewsTreatmentStage(_FakeStorage(), lambda mp: _FakeLlm())

    inp = _input(False, extra={"discarded_news_urls": ["u1"]})
    result = stage.execute(inp)

    assert result.status == "SUCCESS"
    assert result.data["news_markdowns"] == []


# ---------------------------------------------------------------------------
# Modo LLM
# ---------------------------------------------------------------------------

def test_llm_mode_treats_and_persists_with_proc_id():
    """No modo LLM, documentos pendentes são tratados e persistidos com proc_id."""
    llm = _FakeLlm()
    storage = _FakeStorage()
    stage = NewsTreatmentStage(storage, lambda mp: llm)

    result = stage.execute(_input(True))
    entry = result.data["news_markdowns"][0]

    assert result.status == "SUCCESS"
    assert entry["treated"] is True
    assert entry["markdown"].startswith("---")
    assert llm.calls == 1
    assert storage.saved["u1"].proc_id == "run-1"
    assert storage.saved["u1"].title == "T"


def test_llm_not_called_when_doc_already_exists():
    """Documento já persistido é reutilizado; LLM não é chamado."""
    llm = _FakeLlm()
    storage = _FakeStorage({"u1": _TREATED_RECORD})
    stage = NewsTreatmentStage(storage, lambda mp: llm)

    result = stage.execute(_input(True))

    assert result.status == "SUCCESS"
    assert llm.calls == 0


# ---------------------------------------------------------------------------
# Reutilização de documento existente
# ---------------------------------------------------------------------------

def test_reuses_existing_treated_doc_and_restamps_run():
    """Documento tratado anterior é reutilizado e re-carimbado com o proc_id atual."""
    llm = _FakeLlm()
    storage = _FakeStorage({"u1": _TREATED_RECORD})
    stage = NewsTreatmentStage(storage, lambda mp: llm)

    result = stage.execute(_input(False))
    entry = result.data["news_markdowns"][0]

    assert result.status == "SUCCESS"
    assert entry["treated"] is True
    assert "TRATADO" in entry["markdown"]
    assert llm.calls == 0
    assert storage.saved["u1"].proc_id == "run-1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
