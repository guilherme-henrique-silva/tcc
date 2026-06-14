"""Timeline builder — monta o JSON KnightLab das notícias negativas de BBAS3."""

from datetime import date, datetime
from typing import Dict, List, Optional


def _to_date(value) -> Optional[date]:
    """Coerce a value into a date (Rule 1)."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def is_negative_event(news_row: Dict) -> bool:
    """Notícia negativa coincidente com queda de BBAS3."""
    sentiment = news_row.get("SentimentScore")
    variacao = news_row.get("Variacao_Pct_BBAS3")

    if sentiment is None or variacao is None:
        return False

    return int(sentiment) == -1 and float(variacao) < 0


def _build_event(news_row: Dict) -> Optional[Dict]:
    """Build a single KnightLab event from a news row (Rule 1)."""
    event_date = _to_date(news_row.get("date"))

    if event_date is None:
        return None

    headline = news_row.get("headline") or news_row.get("title") or "Notícia"
    variacao = float(news_row.get("Variacao_Pct_BBAS3", 0.0))
    summary = news_row.get("summary", "")

    text = f"{summary} Variação observada de BBAS3 no dia: {variacao:.2f}%.".strip()

    return {
        "start_date": {
            "year": str(event_date.year),
            "month": str(event_date.month),
            "day": str(event_date.day),
        },
        "text": {
            "headline": headline,
            "text": text,
        },
    }


def build_timeline_json(
    news_rows: List[Dict],
    title_year: str = "",
) -> Dict:
    """Monta o dict KnightLab a partir das notícias negativas."""
    events = []

    for row in news_rows:
        if not is_negative_event(row):
            continue

        event = _build_event(row)

        if event is not None:
            events.append(event)

    return {
        "title": {
            "text": {
                "headline": "Notícias com impacto negativo em BBAS3",
                "text": title_year,
            }
        },
        "events": events,
    }
