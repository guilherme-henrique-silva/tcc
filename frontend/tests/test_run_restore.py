"""Testes dos helpers puros de recarga de execução (sem Streamlit)."""

import sys
from datetime import date
from pathlib import Path

_FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(_FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(_FRONTEND_DIR))

from components import run_restore as rr  # noqa: E402

TODAY = date(2026, 11, 15)
A, B = "https://g1/a", "https://info/b"


def _state(**overrides):
    state = {
        "proc_id": "4f1a78da-749b-484f-8542-700ea694f078",
        "status": "SUCCESS",
        "started_at": "2026-11-15T21:27:16.757960",
        "finished_at": "2026-11-15T21:29:32.564625",
        "date_start": "2025-01-01",
        "date_end": "2025-03-31",
        "news_links_count": 2,
        "enabled_stages": ["docling_transform"],
        "news_links": {"2025-01-03": [A, {"url": B, "time": "18:42"}]},
        "treated_news": {A: "---\ntitle: T\n---\nCorpo"},
        "run_result": {"pipeline_id": "4f1a78da", "status": "SUCCESS", "stages_executed": []},
        "has_granger_report": True,
    }
    state.update(overrides)
    return state


def test_session_updates_fill_the_keys_the_pages_already_read():
    updates = rr.session_updates(_state(), TODAY)

    assert updates["news_links"] == {"2025-01-03": [A, {"url": B, "time": "18:42"}]}
    assert updates["treated_md"] == {A: "---\ntitle: T\n---\nCorpo"}
    assert updates["run_result"]["status"] == "SUCCESS"
    assert updates["last_proc_id"] == "4f1a78da-749b-484f-8542-700ea694f078"
    assert updates[rr.LOADED_RUN_KEY]["proc_id"] == updates["last_proc_id"]


def test_period_is_restored_into_sidebar_and_upload_keys():
    updates = rr.session_updates(_state(), TODAY)
    period = (date(2025, 1, 1), date(2025, 3, 31))

    assert updates["date_range"] == updates["global_date_range"] == period
    assert updates["acoes_start_date"] == date(2025, 1, 1)  # mínimo aceito pelo seletor


def test_period_end_is_clamped_to_today():
    updates = rr.session_updates(_state(date_end="2027-01-01"), TODAY)

    assert updates["date_range"] == (date(2025, 1, 1), TODAY)


def test_legacy_run_without_period_leaves_the_period_keys_alone():
    updates = rr.session_updates(_state(date_start=None, date_end=None), TODAY)

    assert not {"date_range", "global_date_range", "acoes_start_date"} & set(updates)


def test_period_entirely_in_the_future_is_ignored():
    updates = rr.session_updates(_state(date_start="2027-01-01", date_end="2027-02-01"), TODAY)

    assert "date_range" not in updates


def test_run_without_result_clears_the_previous_one():
    updates = rr.session_updates(_state(run_result=None, treated_news={}), TODAY)

    assert updates["run_result"] is None and updates["treated_md"] == {}


def test_apply_to_session_replaces_previous_state():
    session = {"news_links": {"2020-01-01": ["https://old"]}, "unrelated": 1}

    rr.apply_to_session(session, _state(), TODAY)

    assert session["news_links"] == {"2025-01-03": [A, {"url": B, "time": "18:42"}]}
    assert session["unrelated"] == 1


def test_treated_md_is_a_copy_not_the_state_dict():
    state = _state()

    rr.session_updates(state, TODAY)["treated_md"]["https://new"] = "x"

    assert "https://new" not in state["treated_news"]


def test_run_label_shows_time_status_and_links():
    label = rr.run_label(_state())

    assert label == "15/11/2026 21:27 · ✅ SUCCESS · 2 link(s)"


def test_run_label_handles_unknown_status():
    assert "❔ UNKNOWN" in rr.run_label(_state(status="UNKNOWN"))


def test_describe_mentions_treated_and_granger():
    text = rr.describe(_state())

    assert "`4f1a78da`" in text and "1 tratada(s)" in text and "Granger" in text
    assert "tratada" not in rr.describe(_state(treated_news={}, has_granger_report=False))
