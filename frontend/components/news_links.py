"""Helpers puros (sem Streamlit) para o dicionário de links agrupados por data.

O estado da sessão ``st.session_state["news_links"]`` é um ``Dict[str, List[str]]``
cuja chave é a data de publicação ISO (``YYYY-MM-DD``) e o valor, os links daquela data.
As regras espelham as do backend (``NewsLinksByDate``): data ISO válida e não futura,
valores em lista de strings não vazias e a mesma URL em uma única data.
"""

import json
import re
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Tuple, Union

NewsLinks = Dict[str, List[str]]

_ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


def flatten(groups: NewsLinks) -> List[str]:
    """URLs em ordem crescente de data e, na data, na ordem informada."""
    return [url for day in sorted(groups) for url in groups[day]]


def date_of(groups: NewsLinks, url: str) -> Optional[str]:
    """Data (ISO) em que a URL está registrada, ou None."""
    for day, links in groups.items():
        if url in links:
            return day

    return None


def add_group(
    groups: NewsLinks,
    day: Union[date, str],
    links: Iterable[str],
    today: Optional[date] = None,
) -> NewsLinks:
    """Devolve uma cópia de ``groups`` com ``links`` mesclados na data ``day``.

    Rejeita (``ValueError``) data futura/malformada e URL já presente em **outra** data;
    URLs repetidas na mesma data são colapsadas. Links vazios são ignorados.
    """
    key = _validate_day(day.isoformat() if isinstance(day, date) else day, today)
    cleaned = [link.strip() for link in links if isinstance(link, str) and link.strip()]

    merged = {d: list(urls) for d, urls in groups.items()}
    bucket = merged.setdefault(key, [])

    for url in cleaned:
        owner = date_of(merged, url)
        if owner is not None and owner != key:
            raise ValueError(
                f"A URL '{url}' já está registrada em {owner}; "
                "uma notícia só pode ter uma data de publicação."
            )
        if url not in bucket:
            bucket.append(url)

    if not bucket:
        del merged[key]

    return merged


def remove_group(groups: NewsLinks, day: str) -> NewsLinks:
    """Devolve uma cópia sem a data ``day`` (e seus links)."""
    return {d: list(urls) for d, urls in groups.items() if d != day}


def remove_link(groups: NewsLinks, day: str, url: str) -> NewsLinks:
    """Devolve uma cópia sem ``url`` em ``day``; a data some quando fica vazia."""
    result: NewsLinks = {}

    for d, urls in groups.items():
        remaining = [u for u in urls if not (d == day and u == url)]
        if remaining:
            result[d] = remaining

    return result


def parse_json(text: str, today: Optional[date] = None) -> NewsLinks:
    """Importa o JSON ``{"YYYY-MM-DD": ["url", ...]}`` aplicando as regras do backend.

    Texto vazio gera ``{}``. Qualquer violação levanta ``ValueError`` (PT-BR), sem
    efeito colateral — quem chama decide se substitui o estado da sessão.
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
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(
                    f"Item inválido na data '{raw_day}': cada link deve ser uma string "
                    f"não vazia (recebido: {item!r})."
                )
        groups = add_group(groups, raw_day, value, today)

    return groups


def summary(groups: NewsLinks) -> Tuple[int, int]:
    """(total de links, total de datas)."""
    return sum(len(urls) for urls in groups.values()), len(groups)


def dates_outside(groups: NewsLinks, start: date, end: date) -> List[str]:
    """Datas (ISO, ordenadas) fora do período de análise ``[start, end]``."""
    return [day for day in sorted(groups) if not start <= date.fromisoformat(day) <= end]


def to_br(day: str) -> str:
    """Converte ``YYYY-MM-DD`` em ``DD-MM-AAAA`` (formato do frontmatter)."""
    return date.fromisoformat(day).strftime("%d-%m-%Y")


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
