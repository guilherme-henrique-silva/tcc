"""Calendário de pregões e alinhamento das notícias ao pregão da B3 (funções puras).

Regra do TCC: notícia de fim de semana, feriado ou publicada depois do fechamento
vai para o **pregão seguinte**. A fonte de verdade do calendário é o conjunto de datas
com cotação do ativo alvo (já exclui fins de semana e feriados da B3, sem tabela de
feriados).
"""

from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime, time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from src.domain.models import News

AUDIT_KEYS = (
    "total",
    "assigned",
    "same_day",
    "moved_weekend_holiday",
    "moved_after_close",
    "before_first_session",
    "without_time",
    "discarded_after_last_session",
)


def parse_close_time(value: object) -> time:
    """Converte "HH:MM" (ou ``time``) no horário de corte; ValueError se inválido."""
    if isinstance(value, time):
        return value

    try:
        return time.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(
            f"MARKET_CLOSE_TIME inválido: '{value}' (use HH:MM, ex.: 17:00)."
        ) from exc


def session_calendar(prices: Iterable) -> List[date]:
    """Datas distintas e ordenadas com cotação (``StockPrice``) — o calendário de pregões."""
    return sorted({_as_date(price.date) for price in prices})


def align_news_to_sessions(
    news: Sequence[News],
    sessions: Sequence[date],
    close_time: time,
) -> Dict[date, List[News]]:
    """Atribui cada notícia a um pregão. Veja ``align_news_with_audit`` para a auditoria."""
    return align_news_with_audit(news, sessions, close_time)[0]


def align_news_with_audit(
    news: Sequence[News],
    sessions: Sequence[date],
    close_time: time,
) -> Tuple[Dict[date, List[News]], Dict[str, int]]:
    """Alinha as notícias aos pregões e devolve ``(pregão -> notícias, auditoria)``.

    Para a data de publicação ``d`` e o horário ``h`` (opcional):

    ============================================================  =====================
    Situação                                                      Pregão atribuído
    ============================================================  =====================
    ``d`` é pregão e (``h`` ausente ou ``h`` <= ``close_time``)   ``d``
    ``d`` é pregão e ``h`` > ``close_time``                       1º pregão depois de d
    ``d`` não é pregão (fim de semana/feriado)                    1º pregão depois de d
    não existe pregão posterior dentro do período                 descartada (contada)
    ``d`` anterior ao primeiro pregão do período                  1º pregão
    ============================================================  =====================

    Notícia sem horário em dia de pregão é tratada como "durante o pregão".
    """
    ordered = sorted(set(sessions))
    session_set = set(ordered)
    audit = {key: 0 for key in AUDIT_KEYS}
    by_session: Dict[date, List[News]] = defaultdict(list)

    for item in news:
        audit["total"] += 1
        published_day = _as_date(item.published_date)
        published_time = getattr(item, "published_time", None)

        if published_time is None:
            audit["without_time"] += 1

        target, reason = _assign(
            published_day, published_time, ordered, session_set, close_time
        )
        audit[reason] += 1

        if target is not None:
            audit["assigned"] += 1
            by_session[target].append(item)

    return dict(by_session), audit


def _assign(
    published_day: date,
    published_time: Optional[time],
    ordered: List[date],
    session_set: set,
    close_time: time,
) -> Tuple[Optional[date], str]:
    """Pregão de destino (ou None) e a chave de auditoria que explica a decisão."""
    if not ordered:
        return None, "discarded_after_last_session"

    if published_day < ordered[0]:
        return ordered[0], "before_first_session"

    if published_day in session_set:
        if published_time is None or published_time <= close_time:
            return published_day, "same_day"

        return _next_session(published_day, ordered, "moved_after_close")

    return _next_session(published_day, ordered, "moved_weekend_holiday")


def _next_session(
    day: date,
    ordered: List[date],
    reason: str,
) -> Tuple[Optional[date], str]:
    """Primeiro pregão estritamente posterior a ``day``; descartada se não houver."""
    index = bisect_right(ordered, day)

    if index >= len(ordered):
        return None, "discarded_after_last_session"

    return ordered[index], reason


def _as_date(value: object) -> date:
    """``datetime`` (com ou sem fuso) -> ``date`` civil local; ``date`` passa direto."""
    if isinstance(value, datetime):
        return value.date()

    return value
