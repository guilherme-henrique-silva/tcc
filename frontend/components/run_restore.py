"""Recarga de uma execução anterior da pipeline na sessão do Streamlit (sem Streamlit).

O backend guarda tudo no banco, mas a sessão do frontend começa vazia depois de uma
reinicialização. Estes helpers puros traduzem o estado devolvido por
``GET /api/pipeline/runs/...`` nas chaves de ``st.session_state`` que as páginas já leem
(``news_links``, ``run_result``, ``treated_md``, ``last_proc_id``, período), de modo que
nenhuma página precisa saber que os dados vieram de uma recarga.
"""

from datetime import date, datetime
from typing import Any, Dict, MutableMapping, Optional

LOADED_RUN_KEY = "loaded_run"

_STATUS_ICON = {
    "SUCCESS": "✅",
    "FAILED": "❌",
    "BLOCKED": "⏸️",
    "RUNNING": "⏳",
}


def run_label(run: Dict[str, Any]) -> str:
    """Rótulo de uma execução no seletor: data/hora, status e quantidade de links."""
    icon = _STATUS_ICON.get(run.get("status", ""), "❔")

    return (
        f"{format_timestamp(run['started_at'])} · {icon} {run.get('status', 'UNKNOWN')} · "
        f"{run.get('news_links_count', 0)} link(s)"
    )


def format_timestamp(value: str) -> str:
    """ISO datetime -> ``DD/MM/AAAA HH:MM``."""
    return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")


def describe(state: Dict[str, Any]) -> str:
    """Legenda curta da execução carregada, para a sidebar."""
    parts = [
        f"`{state['proc_id'][:8]}`",
        format_timestamp(state["started_at"]),
        f"{_STATUS_ICON.get(state.get('status', ''), '❔')} {state.get('status', 'UNKNOWN')}",
        f"{state.get('news_links_count', 0)} link(s)",
    ]

    if state.get("treated_news"):
        parts.append(f"{len(state['treated_news'])} tratada(s)")

    if state.get("has_granger_report"):
        parts.append("com relatório de Granger")

    return " · ".join(parts)


def session_updates(
    state: Dict[str, Any],
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Chaves de ``session_state`` que reproduzem a execução ``state``.

    O período só é restaurado quando a execução o registrou (as anteriores à recarga não
    têm) e é limitado a ``today`` — a UI não aceita datas futuras.
    """
    updates: Dict[str, Any] = {
        "news_links": state.get("news_links") or {},
        "treated_md": dict(state.get("treated_news") or {}),
        "run_result": state.get("run_result"),
        "last_proc_id": state["proc_id"],
        LOADED_RUN_KEY: state,
    }
    updates.update(_period_updates(state, today or date.today()))

    return updates


def apply_to_session(
    session: MutableMapping[str, Any],
    state: Dict[str, Any],
    today: Optional[date] = None,
) -> None:
    """Grava na sessão o estado da execução recarregada."""
    for key, value in session_updates(state, today).items():
        session[key] = value


def _period_updates(state: Dict[str, Any], today: date) -> Dict[str, Any]:
    """Período analisado da execução, nas chaves usadas pela sidebar e pelo upload."""
    if not state.get("date_start") or not state.get("date_end"):
        return {}

    start = date.fromisoformat(state["date_start"])
    end = min(date.fromisoformat(state["date_end"]), today)

    if start > end:
        return {}

    return {
        "date_range": (start, end),
        "acoes_start_date": start,
        "global_date_range": (start, end),
    }
