"""Helpers puros (sem Streamlit) para o dicionário de links agrupados por data.

O estado da sessão ``st.session_state["news_links"]`` é um ``Dict[str, List[Item]]`` cuja
chave é a data de publicação ISO (``YYYY-MM-DD``). Cada ``Item`` é:

* ``str`` — a URL, com horário de publicação desconhecido (formato legado); ou
* ``{"url": str, "time": "HH:MM"}`` — a URL com o horário (24h, **horário de Brasília**).

Os dois formatos podem ser misturados. As regras espelham as do backend
(``NewsLinksByDate``): data ISO válida e não futura, URL não vazia, ``time`` em ``HH:MM``
válido e a mesma URL em uma única data.
"""

import json
import re
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Tuple, Union

Item = Union[str, Dict[str, str]]
NewsLinks = Dict[str, List[Item]]

_ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
_HH_MM = re.compile(r"\d{2}:\d{2}")
# Atalho da entrada manual: "18:42 https://..." (horário, espaço, URL).
_TIME_PREFIX = re.compile(r"(\d{2}:\d{2})\s+(\S.*)")
_ITEM_KEYS = {"url", "time"}


def url_of(item: Item) -> str:
    """URL de um item (string ou objeto)."""
    return item["url"] if isinstance(item, dict) else item


def time_of(item: Item) -> Optional[str]:
    """Horário ``HH:MM`` do item, ou None quando desconhecido."""
    return item.get("time") if isinstance(item, dict) else None


def make_item(url: str, when: Optional[str] = None) -> Item:
    """String quando não há horário; objeto ``{"url", "time"}`` quando há."""
    return {"url": url, "time": when} if when else url


def parse_entry(text: str) -> Tuple[str, Optional[str]]:
    """Separa o atalho ``HH:MM url`` em ``(url, "HH:MM")``; sem horário, ``(url, None)``.

    Levanta ``ValueError`` quando o prefixo parece horário mas é inválido (ex.: ``25:10``).
    """
    stripped = text.strip()
    match = _TIME_PREFIX.fullmatch(stripped)

    if not match:
        return stripped, None

    when, url = match.groups()
    return url.strip(), validate_time(when, url.strip())


def validate_time(value: object, url: str = "") -> str:
    """Valida ``HH:MM`` (24h) e devolve o texto aparado; ValueError (PT-BR) se inválido."""
    where = f" (URL {url})" if url else ""
    text = value.strip() if isinstance(value, str) else ""

    if not _HH_MM.fullmatch(text):
        raise ValueError(
            f"Horário inválido '{value}'{where}: use HH:MM, 24h, horário de Brasília (ex.: 18:42)."
        )

    hours, minutes = (int(part) for part in text.split(":"))
    if hours > 23 or minutes > 59:
        raise ValueError(
            f"Horário inválido '{value}'{where}: horas entre 00 e 23 e minutos entre 00 e 59."
        )

    return text


def flatten(groups: NewsLinks) -> List[str]:
    """URLs em ordem crescente de data e, na data, na ordem informada."""
    return [url_of(item) for day in sorted(groups) for item in groups[day]]


def date_of(groups: NewsLinks, url: str) -> Optional[str]:
    """Data (ISO) em que a URL está registrada, ou None."""
    for day, items in groups.items():
        if any(url_of(item) == url for item in items):
            return day

    return None


def add_group(
    groups: NewsLinks,
    day: Union[date, str],
    links: Iterable[Item],
    today: Optional[date] = None,
) -> NewsLinks:
    """Devolve uma cópia de ``groups`` com ``links`` mesclados na data ``day``.

    Cada link pode ser ``str`` (aceita o atalho ``HH:MM url``) ou ``{"url", "time"}``.
    Rejeita (``ValueError``) data futura/malformada, horário inválido e URL já presente em
    **outra** data; URLs repetidas na mesma data são colapsadas (o horário informado
    prevalece sobre o desconhecido). Links vazios são ignorados.
    """
    key = _validate_day(day.isoformat() if isinstance(day, date) else day, today)

    merged: NewsLinks = {d: [_copy(i) for i in items] for d, items in groups.items()}
    bucket = merged.setdefault(key, [])

    for raw in links:
        parsed = _parse_link(raw)
        if parsed is None:
            continue

        url, when = parsed
        owner = date_of(merged, url)
        if owner is not None and owner != key:
            raise ValueError(
                f"A URL '{url}' já está registrada em {owner}; "
                "uma notícia só pode ter uma data de publicação."
            )

        _upsert(bucket, url, when)

    if not bucket:
        del merged[key]

    return merged


def remove_group(groups: NewsLinks, day: str) -> NewsLinks:
    """Devolve uma cópia sem a data ``day`` (e seus links)."""
    return {d: [_copy(i) for i in items] for d, items in groups.items() if d != day}


def remove_link(groups: NewsLinks, day: str, url: str) -> NewsLinks:
    """Devolve uma cópia sem ``url`` em ``day``; a data some quando fica vazia."""
    result: NewsLinks = {}

    for d, items in groups.items():
        remaining = [_copy(i) for i in items if not (d == day and url_of(i) == url)]
        if remaining:
            result[d] = remaining

    return result


def parse_json(text: str, today: Optional[date] = None) -> NewsLinks:
    """Importa o JSON ``{"YYYY-MM-DD": [item, ...]}`` aplicando as regras do backend.

    Cada item é uma URL ou ``{"url": ..., "time": "HH:MM"}``. Texto vazio gera ``{}``.
    Qualquer violação levanta ``ValueError`` (PT-BR), sem efeito colateral — quem chama
    decide se substitui o estado da sessão.
    """
    if not text or not text.strip():
        return {}

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido ({exc.msg}, linha {exc.lineno}).") from exc

    if not isinstance(payload, dict):
        raise ValueError(
            'O JSON deve ser um objeto no formato {"YYYY-MM-DD": ["url", ...]}; '
            "listas de links não são aceitas."
        )

    groups: NewsLinks = {}
    for raw_day, value in payload.items():
        if not isinstance(value, list):
            raise ValueError(f"Os links da data '{raw_day}' devem ser uma lista de URLs.")

        items = [_json_item(raw_day, item) for item in value]
        groups = add_group(groups, raw_day, items, today)

    return groups


def summary(groups: NewsLinks) -> Tuple[int, int]:
    """(total de links, total de datas)."""
    return sum(len(items) for items in groups.values()), len(groups)


def timed_count(groups: NewsLinks) -> int:
    """Quantos links têm horário de publicação informado."""
    return sum(1 for items in groups.values() for item in items if time_of(item))


def dates_outside(groups: NewsLinks, start: date, end: date) -> List[str]:
    """Datas (ISO, ordenadas) fora do período de análise ``[start, end]``."""
    return [day for day in sorted(groups) if not start <= date.fromisoformat(day) <= end]


def to_br(day: str) -> str:
    """Converte ``YYYY-MM-DD`` em ``DD-MM-AAAA`` (formato do frontmatter)."""
    return date.fromisoformat(day).strftime("%d-%m-%Y")


# ---------------------------------------------------------------------- #
# Internos                                                                #
# ---------------------------------------------------------------------- #
def _copy(item: Item) -> Item:
    return dict(item) if isinstance(item, dict) else item


def _parse_link(raw: object) -> Optional[Tuple[str, Optional[str]]]:
    """``(url, horário)`` de um link da entrada manual; None quando vazio."""
    if isinstance(raw, dict):
        url = raw.get("url")
        if not isinstance(url, str) or not url.strip():
            return None
        when = raw.get("time")
        return url.strip(), (validate_time(when, url.strip()) if when else None)

    if isinstance(raw, str) and raw.strip():
        return parse_entry(raw)

    return None


def _upsert(bucket: List[Item], url: str, when: Optional[str]) -> None:
    """Acrescenta a URL ao grupo, ou só completa o horário de uma já existente."""
    for index, existing in enumerate(bucket):
        if url_of(existing) != url:
            continue

        if when and not time_of(existing):
            bucket[index] = make_item(url, when)
        return

    bucket.append(make_item(url, when))


def _json_item(raw_day: str, item: object) -> Item:
    """Valida um item do JSON importado (string ou objeto) e o devolve normalizado."""
    if isinstance(item, dict):
        unknown = sorted(str(k) for k in item if k not in _ITEM_KEYS)
        if unknown:
            raise ValueError(
                f"Item inválido na data '{raw_day}': chave(s) desconhecida(s) {unknown}; "
                'use apenas "url" e "time".'
            )
        url = item.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError(
                f"Item inválido na data '{raw_day}': o campo \"url\" é obrigatório "
                f"(recebido: {url!r})."
            )
        when = item.get("time")
        return make_item(url.strip(), validate_time(when, url.strip()) if when is not None else None)

    if not isinstance(item, str) or not item.strip():
        raise ValueError(
            f"Item inválido na data '{raw_day}': cada link deve ser uma string "
            f"não vazia (recebido: {item!r})."
        )

    return item.strip()


def _validate_day(day: object, today: Optional[date]) -> str:
    """Valida a chave como data ISO existente e não futura; devolve a própria chave."""
    try:
        if not isinstance(day, str) or not _ISO_DAY.fullmatch(day):
            raise ValueError(day)
        parsed = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(
            f"Data inválida '{day}': use o formato ISO YYYY-MM-DD (ex.: 2026-11-03)."
        ) from exc

    limit = today or date.today()
    if parsed > limit:
        raise ValueError(f"Data '{day}' está no futuro (hoje é {limit.isoformat()}).")

    return day
