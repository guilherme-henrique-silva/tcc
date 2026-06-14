"""Testes do CsvNewsAdapter — validação de colunas obrigatórias."""

from datetime import date

import pandas as pd
import pytest

from backend.src.adapters.data_sources.csv_news_adapter import CsvNewsAdapter
from backend.src.domain.value_objects.date_range import DateRange


def _date_range() -> DateRange:
    return DateRange(start_date=date(2025, 1, 1), end_date=date(2025, 12, 31))


def _make_row(**overrides) -> dict:
    row = {
        "date": "2025-06-01",
        "title": "Título",
        "content": "Conteúdo da notícia",
        "source": "Portal",
        "url": "https://example.com/noticia",
        "sentiment": 0,
    }
    row.update(overrides)
    return row


def _convert(rows: list) -> list:
    adapter = CsvNewsAdapter()
    return adapter._convert_to_news_items(pd.DataFrame(rows), _date_range())


class TestCsvNewsAdapterUrlRequired:
    """url é chave primária; linhas sem url válido devem ser descartadas silenciosamente."""

    def test_row_with_valid_url_included(self):
        assert len(_convert([_make_row()])) == 1

    def test_row_without_url_key_discarded(self):
        row = {k: v for k, v in _make_row().items() if k != "url"}
        assert len(_convert([row])) == 0

    def test_row_with_empty_url_discarded(self):
        assert len(_convert([_make_row(url="")])) == 0

    def test_row_with_whitespace_url_discarded(self):
        assert len(_convert([_make_row(url="   ")])) == 0

    def test_mixed_rows_only_valid_urls_included(self):
        rows = [
            _make_row(url="https://a.com/1"),
            _make_row(url=""),
            _make_row(url="https://b.com/2"),
        ]
        assert len(_convert(rows)) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
