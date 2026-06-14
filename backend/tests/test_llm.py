"""Testes do port de LLM, adapters e catálogo — sem rede nem download (Requisito 13)."""

import os

import pytest

from backend.src.adapters.llm.catalog import (
    disk_status,
    list_with_status,
    find_by_path,
    repo_id_for,
    STATUS_READY,
    STATUS_DOWNLOAD,
    STATUS_DOWNLOADING,
)
from backend.src.adapters.llm import LocalLlmAdapter, ApiLlmAdapter
from backend.app.core.config import Config


class TestCatalog:
    """Parsing de LLM_MODELS e detecção de status em disco."""

    def test_disk_status(self, tmp_path):
        (tmp_path / "llm-models" / "qwen").mkdir(parents=True)
        (tmp_path / "llm-models" / "qwen" / "config.json").write_text("{}")
        models_dir = str(tmp_path / "llm-models")

        assert disk_status(models_dir, "llm-models/qwen", ()) == STATUS_READY
        assert disk_status(models_dir, "llm-models/none", ()) == STATUS_DOWNLOAD
        assert disk_status(models_dir, "llm-models/none", ("llm-models/none",)) == STATUS_DOWNLOADING

    def test_list_with_status_and_helpers(self, tmp_path):
        models = [{"name": "Q", "path": "llm-models/q", "vram": "8 GB", "best_use": "x"}]
        enriched = list_with_status(models, str(tmp_path / "llm-models"), ())

        assert enriched[0]["status"] == STATUS_DOWNLOAD
        assert find_by_path(models, "llm-models/q")["name"] == "Q"
        assert repo_id_for({"path": "llm-models/q"}) == "q"
        assert repo_id_for({"path": "x", "repo": "Org/Q"}) == "Org/Q"

    def test_config_llm_models_parsing(self, monkeypatch):
        monkeypatch.setattr(
            Config, "LLM_MODELS",
            '[{"name":"Q","path":"p","vram":"8 GB","best_use":"x"}]',
        )
        models = Config.llm_models()
        assert models[0]["name"] == "Q"

        monkeypatch.setattr(Config, "LLM_MODELS", "not json")
        assert Config.llm_models() == []

        monkeypatch.setattr(Config, "LLM_MODELS", "")
        assert Config.llm_models() == []


class TestLocalAdapter:
    """LocalLlmAdapter mockado: não baixa nem carrega pesos reais."""

    def test_treats_with_injected_collaborators(self, tmp_path):
        calls = {"download": 0}

        def fake_download(*, repo_id, local_dir):
            os.makedirs(local_dir, exist_ok=True)
            open(os.path.join(local_dir, "weights"), "w").close()
            calls["download"] += 1

        def fake_builder(model_dir, device):
            return lambda text: [{"generated_text": "tratado"}]

        adapter = LocalLlmAdapter(
            "llm-models/m",
            str(tmp_path / "llm-models"),
            repo_id="org/m",
            snapshot_download=fake_download,
            pipeline_builder=fake_builder,
        )

        assert adapter.treat_news("bruto", prompt="P") == "tratado"
        assert calls["download"] == 1

    def test_does_not_redownload_when_present(self, tmp_path):
        model_dir = tmp_path / "llm-models" / "m"
        model_dir.mkdir(parents=True)
        (model_dir / "weights").write_text("x")
        calls = {"download": 0}

        def fake_download(*, repo_id, local_dir):
            calls["download"] += 1

        adapter = LocalLlmAdapter(
            "llm-models/m",
            str(tmp_path / "llm-models"),
            snapshot_download=fake_download,
            pipeline_builder=lambda d, dev: (lambda text: [{"generated_text": "ok"}]),
        )
        adapter.treat_news("x", prompt="P")

        assert calls["download"] == 0  # já presente em disco → não rebaixa


class TestApiAdapter:
    """ApiLlmAdapter via Pydantic AI usando TestModel (sem rede)."""

    def test_treats_with_testmodel(self):
        from pydantic_ai import Agent
        from pydantic_ai.models.test import TestModel

        agent = Agent(TestModel(), result_type=str)
        adapter = ApiLlmAdapter("anthropic", "claude-sonnet-4-6", agent=agent)

        output = adapter.treat_news("bruto", prompt="P")
        assert isinstance(output, str)
        assert output


class TestVramTier:
    """VramTier enum: parsing de string de VRAM e propriedade recommendation."""

    def test_light_tier_at_boundary(self):
        from backend.src.adapters.llm.vram_tier import VramTier

        assert VramTier.from_vram_string("4 GB") is VramTier.LIGHT

    def test_balanced_tier_at_boundary(self):
        from backend.src.adapters.llm.vram_tier import VramTier

        assert VramTier.from_vram_string("8 GB") is VramTier.BALANCED

    def test_advanced_tier_above_boundary(self):
        from backend.src.adapters.llm.vram_tier import VramTier

        assert VramTier.from_vram_string("16 GB") is VramTier.ADVANCED

    def test_empty_string_defaults_to_balanced(self):
        from backend.src.adapters.llm.vram_tier import VramTier

        assert VramTier.from_vram_string("") is VramTier.BALANCED

    def test_none_like_string_defaults_to_balanced(self):
        from backend.src.adapters.llm.vram_tier import VramTier

        assert VramTier.from_vram_string("N/A") is VramTier.BALANCED

    def test_recommendation_is_non_empty_string(self):
        from backend.src.adapters.llm.vram_tier import VramTier

        for tier in VramTier:
            assert isinstance(tier.recommendation, str)
            assert len(tier.recommendation) > 0

    def test_recommendation_texts_are_distinct(self):
        from backend.src.adapters.llm.vram_tier import VramTier

        texts = [tier.recommendation for tier in VramTier]
        assert len(texts) == len(set(texts))


class TestNewsCategory:
    """NewsCategory enum: valores, tipo e lookup por string."""

    def test_all_five_values_present(self):
        from backend.src.adapters.llm.news_category import NewsCategory

        values = {c.value for c in NewsCategory}
        assert values == {
            "finanças",
            "macroeconomia",
            "microeconomia",
            "política",
            "agronegócio",
            "tecnologia"
        }

    def test_is_str_enum(self):
        from backend.src.adapters.llm.news_category import NewsCategory

        assert isinstance(NewsCategory.FINANCAS, str)
        assert NewsCategory.FINANCAS == "finanças"

    def test_str_lookup(self):
        from backend.src.adapters.llm.news_category import NewsCategory

        assert NewsCategory("macroeconomia") is NewsCategory.MACROECONOMIA


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
