"""Testes dos helpers puros do dicionário de links por data (sem Streamlit)."""

import sys
from datetime import date
from pathlib import Path

import pytest

_FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(_FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(_FRONTEND_DIR))

from components import news_links as nl  # noqa: E402

TODAY = date(2026, 11, 4)
A, B, C = "https://g1/a", "https://info/b", "https://g1/c"


def test_flatten_orders_by_date_then_given_order():
    groups = {"2026-11-04": [C], "2026-11-01": [B, A]}

    assert nl.flatten(groups) == [B, A, C]


def test_date_of():
    groups = {"2026-11-01": [A]}

    assert nl.date_of(groups, A) == "2026-11-01"
    assert nl.date_of(groups, B) is None


def test_add_group_merges_and_collapses_without_mutating():
    original = {"2026-11-01": [A]}

    result = nl.add_group(original, date(2026, 11, 1), [f" {B} ", A, B, ""], TODAY)

    assert result == {"2026-11-01": [A, B]}
    assert original == {"2026-11-01": [A]}


def test_add_group_rejects_url_in_other_date():
    with pytest.raises(ValueError, match="2026-11-01"):
        nl.add_group({"2026-11-01": [A]}, "2026-11-02", [A], TODAY)


def test_add_group_rejects_future_and_malformed_date():
    with pytest.raises(ValueError, match="futuro"):
        nl.add_group({}, "2026-11-05", [A], TODAY)
    with pytest.raises(ValueError, match="inválida"):
        nl.add_group({}, "03/11/2026", [A], TODAY)
    with pytest.raises(ValueError, match="inválida"):
        nl.add_group({}, "20261103", [A], TODAY)


def test_add_group_with_no_links_does_not_create_the_date():
    assert nl.add_group({}, "2026-11-01", ["", "  "], TODAY) == {}


def test_remove_group_and_link():
    groups = {"2026-11-01": [A, B], "2026-11-02": [C]}

    assert nl.remove_group(groups, "2026-11-01") == {"2026-11-02": [C]}
    assert nl.remove_link(groups, "2026-11-01", A) == {"2026-11-01": [B], "2026-11-02": [C]}
    assert nl.remove_link(groups, "2026-11-02", C) == {"2026-11-01": [A, B]}


def test_parse_json_valid():
    text = '{"2026-11-03": ["https://g1/a", "https://info/b"], "2026-11-04": ["https://g1/c"]}'

    assert nl.parse_json(text, TODAY) == {
        "2026-11-03": [A, B],
        "2026-11-04": [C],
    }


@pytest.mark.parametrize("text", ["", "   "])
def test_parse_json_empty(text):
    assert nl.parse_json(text, TODAY) == {}


@pytest.mark.parametrize(
    "text",
    [
        "não é json",
        '["https://g1/a"]',
        '{"links": ["https://g1/a"]}',
        '{"2026-11-03": "https://g1/a"}',
        '{"2026-11-03": [1]}',
        '{"2026-11-03": [" "]}',
        '{"2099-01-01": ["https://g1/a"]}',
        '{"03/11/2026": ["https://g1/a"]}',
        '{"2026-11-03": ["https://g1/a"], "2026-11-04": ["https://g1/a"]}',
    ],
)
def test_parse_json_invalid(text):
    with pytest.raises(ValueError):
        nl.parse_json(text, TODAY)


def test_summary():
    assert nl.summary({"2026-11-01": [A, B], "2026-11-02": [C]}) == (3, 2)
    assert nl.summary({}) == (0, 0)


def test_dates_outside_period():
    groups = {"2026-10-01": [A], "2026-11-03": [B], "2026-12-31": [C]}

    assert nl.dates_outside(groups, date(2026, 11, 1), date(2026, 11, 30)) == [
        "2026-10-01",
        "2026-12-31",
    ]


def test_to_br():
    assert nl.to_br("2026-11-03") == "03-11-2026"
