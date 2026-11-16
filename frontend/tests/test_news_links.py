"""Testes dos helpers puros do dicionário de links por data (sem Streamlit)."""

import json
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


# --------------------------------------------------------------------------- #
# Horário de publicação (item string ou {"url", "time"})                       #
# --------------------------------------------------------------------------- #
T = {"url": B, "time": "18:42"}


def test_parse_json_accepts_both_formats_mixed():
    text = '{"2026-11-03": ["https://g1/a", {"url": "https://info/b", "time": "18:42"}]}'

    assert nl.parse_json(text, TODAY) == {"2026-11-03": [A, T]}


def test_parse_json_object_without_time_is_normalized_to_a_string():
    assert nl.parse_json('{"2026-11-03": [{"url": "https://g1/a"}]}', TODAY) == {
        "2026-11-03": [A]
    }


def test_parse_json_accepts_news_links_envelope():
    text = '{"news_links": {"2026-11-03": ["https://g1/a", {"url": "https://info/b", "time": "18:42"}]}}'

    assert nl.parse_json(text, TODAY) == {"2026-11-03": [A, T]}


def test_parse_json_empty_envelope():
    assert nl.parse_json('{"news_links": {}}', TODAY) == {}


@pytest.mark.parametrize(
    "text",
    [
        '{"news_links": ["https://g1/a"]}',
        '{"news_links": {"2026-11-03": ["https://g1/a"]}, "outra": 1}',
    ],
)
def test_parse_json_rejects_malformed_envelope(text):
    with pytest.raises(ValueError):
        nl.parse_json(text, TODAY)


@pytest.mark.parametrize(
    "item",
    [
        '{"url": "https://g1/a", "time": "7:5"}',
        '{"url": "https://g1/a", "time": "25:10"}',
        '{"url": "https://g1/a", "time": "12:60"}',
        '{"url": "https://g1/a", "time": 1842}',
        '{"url": "https://g1/a", "hora": "10:00"}',
        '{"time": "10:00"}',
        '{"url": " "}',
    ],
)
def test_parse_json_rejects_invalid_objects(item):
    with pytest.raises(ValueError):
        nl.parse_json(f'{{"2026-11-03": [{item}]}}', TODAY)


def test_invalid_time_message_is_in_portuguese_and_names_the_url():
    with pytest.raises(ValueError, match="Horário inválido '25:10'.*https://g1/a"):
        nl.parse_json('{"2026-11-03": [{"url": "https://g1/a", "time": "25:10"}]}', TODAY)


def test_manual_shortcut_time_then_url():
    result = nl.add_group({}, date(2026, 11, 3), ["18:42 https://info/b", A], TODAY)

    assert result == {"2026-11-03": [T, A]}


def test_manual_shortcut_with_extra_spaces_and_invalid_time():
    assert nl.add_group({}, "2026-11-03", ["09:05   https://g1/a "], TODAY) == {
        "2026-11-03": [{"url": A, "time": "09:05"}]
    }
    with pytest.raises(ValueError, match="Horário inválido"):
        nl.add_group({}, "2026-11-03", ["25:10 https://g1/a"], TODAY)


def test_plain_url_is_never_taken_for_a_shortcut():
    assert nl.parse_entry("https://g1/a") == (A, None)
    assert nl.parse_entry("18:42 https://g1/a") == (A, "18:42")


def test_add_group_accepts_objects_and_keeps_unknown_time_as_string():
    result = nl.add_group({}, "2026-11-03", [T, {"url": A}, {"url": C, "time": None}], TODAY)

    assert result == {"2026-11-03": [T, A, C]}


def test_repeated_url_gains_the_time_but_never_loses_it():
    first = nl.add_group({}, "2026-11-03", [B], TODAY)
    with_time = nl.add_group(first, "2026-11-03", ["18:42 https://info/b"], TODAY)
    again = nl.add_group(with_time, "2026-11-03", [B], TODAY)

    assert with_time == {"2026-11-03": [T]}
    assert again == {"2026-11-03": [T]}


def test_url_in_other_date_is_rejected_even_with_time():
    with pytest.raises(ValueError, match="2026-11-03"):
        nl.add_group({"2026-11-03": [A]}, "2026-11-04", ["10:00 https://g1/a"], TODAY)


def test_flatten_date_of_and_remove_work_with_timed_items():
    groups = {"2026-11-04": [C], "2026-11-01": [T, A]}

    assert nl.flatten(groups) == [B, A, C]
    assert nl.date_of(groups, B) == "2026-11-01"
    assert nl.remove_link(groups, "2026-11-01", B) == {"2026-11-04": [C], "2026-11-01": [A]}
    assert nl.summary(groups) == (3, 2)
    assert nl.timed_count(groups) == 1


def test_helpers_do_not_mutate_inputs_with_objects():
    original = {"2026-11-01": [dict(T)]}

    nl.add_group(original, "2026-11-01", ["10:00 https://g1/a"], TODAY)
    nl.remove_group(original, "2026-11-01")
    nl.remove_link(original, "2026-11-01", B)

    assert original == {"2026-11-01": [T]}


def test_round_trip_matches_backend_value_object():
    """O JSON que o frontend gera deve ser aceito, sem mudanças, pelo backend."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from src.domain.value_objects import NewsLinksByDate

    groups = nl.add_group({}, "2026-11-03", ["18:42 https://info/b", A], TODAY)

    assert NewsLinksByDate.from_raw(json.loads(json.dumps(groups)), today=TODAY).to_dict() == groups
