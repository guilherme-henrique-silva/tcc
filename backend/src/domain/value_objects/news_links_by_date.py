"""NewsLinksByDate — value object imutável com os links de notícias agrupados por data."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, time
from typing import Dict, List, Optional, Tuple, Union

from .date_range import DateRange

# date.fromisoformat (3.11+) aceita também AAAAMMDD e AAAA-Www-D; a spec exige YYYY-MM-DD.
_ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
_HH_MM = re.compile(r"\d{2}:\d{2}")
_OBJECT_KEYS = frozenset({"url", "time"})

# (url, horário de publicação em Brasília ou None quando desconhecido)
_Link = Tuple[str, Optional[time]]
# Item serializado: string (sem horário) ou objeto {"url": ..., "time": "HH:MM"}.
RawLink = Union[str, Dict[str, str]]


@dataclass(frozen=True)
class NewsLinksByDate:
    """Coleção imutável *data de publicação → links* (first-class collection).

    Formato válido (chaves ISO ``YYYY-MM-DD``; cada item é uma string — horário
    desconhecido — ou um objeto com ``url`` e, opcionalmente, ``time`` em ``HH:MM``
    24h, horário de Brasília; os dois formatos podem ser misturados):

        {
          "2026-11-03": ["https://g1.globo.com/economia/noticia/a.ghtml",
                         {"url": "https://www.infomoney.com.br/mercados/b/",
                          "time": "18:42"}],
          "2026-11-04": ["https://g1.globo.com/economia/noticia/c.ghtml"]
        }

    Construa sempre via ``from_raw``, que valida e normaliza. Formatos legados
    (lista plana, ``{"links": [...]}`` ou string que não é JSON) são rejeitados.
    """

    _groups: Tuple[Tuple[date, Tuple[_Link, ...]], ...] = ()

    @classmethod
    def from_raw(cls, raw: object, today: Optional[date] = None) -> "NewsLinksByDate":
        """Valida ``raw`` (dict ou string JSON) e devolve a coleção normalizada.

        ``None``, string em branco e ``{}`` geram coleção vazia. Violações geram
        ``ValueError`` com mensagem em PT-BR identificando a chave ou URL ofensora.
        """
        payload = cls._load_payload(raw)
        limit = today or date.today()

        groups: Dict[date, List[List[object]]] = {}
        owner_by_url: Dict[str, date] = {}

        for key, value in payload.items():
            day = cls._parse_day(key, limit)
            links = cls._normalize_links(key, value)
            cls._register_links(groups, owner_by_url, day, links)

        ordered = tuple(
            (day, tuple((url, when) for url, when in links))
            for day, links in sorted(groups.items())
            if links
        )
        return cls(ordered)

    def items(self) -> List[Tuple[str, date, Optional[time]]]:
        """Trios ``(url, data, horário)`` por data crescente e, na data, na ordem informada."""
        return [
            (url, day, when)
            for day, links in self._groups
            for url, when in links
        ]

    def urls(self) -> List[str]:
        """URLs na mesma ordem de ``items()``."""
        return [url for url, _, _ in self.items()]

    def time_of(self, url: str) -> Optional[time]:
        """Horário de publicação informado para a URL, ou None (desconhecido/ausente)."""
        for candidate, _, when in self.items():
            if candidate == url:
                return when

        return None

    def dates_outside(self, date_range: DateRange) -> List[date]:
        """Datas fora do período de análise (apenas para avisos; não invalida)."""
        return [day for day, _ in self._groups if not date_range.contains(day)]

    def to_dict(self) -> Dict[str, List[RawLink]]:
        """Serializa com chaves ISO, preservando o formato de ida e volta.

        Item sem horário vira string; item com horário vira ``{"url", "time"}``.
        """
        return {
            day.isoformat(): [self._serialize_link(url, when) for url, when in links]
            for day, links in self._groups
        }

    def is_empty(self) -> bool:
        """Indica se não há nenhuma URL."""
        return len(self) == 0

    def __len__(self) -> int:
        return sum(len(links) for _, links in self._groups)

    # ------------------------------------------------------------------ #
    # Parsing e validação                                                 #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _serialize_link(url: str, when: Optional[time]) -> RawLink:
        """String quando não há horário; objeto ``{"url", "time"}`` quando há."""
        if when is None:
            return url

        return {"url": url, "time": when.strftime("%H:%M")}

    @staticmethod
    def _load_payload(raw: object) -> dict:
        """Converte a entrada bruta em ``dict``; vazio para None/branco."""
        if raw is None:
            return {}

        if isinstance(raw, str):
            return NewsLinksByDate._load_json(raw)

        if isinstance(raw, dict):
            return raw

        raise ValueError(
            "news_links deve ser um objeto JSON no formato "
            '{"YYYY-MM-DD": ["url", ...]}; '
            f"recebido: {type(raw).__name__} (formato de lista não é mais aceito)."
        )

    @staticmethod
    def _load_json(text: str) -> dict:
        """Faz o parse de uma string JSON que precisa conter um objeto."""
        stripped = text.strip()

        if not stripped:
            return {}

        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"news_links não é um JSON válido ({exc.msg}, posição {exc.pos}); "
                'esperado {"YYYY-MM-DD": ["url", ...]}.'
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                "news_links deve ser um objeto JSON no formato "
                '{"YYYY-MM-DD": ["url", ...]}; '
                f"recebido: {type(parsed).__name__} (formato de lista não é mais aceito)."
            )

        return parsed

    @staticmethod
    def _parse_day(key: object, today: date) -> date:
        """Valida a chave como data ISO existente e não futura."""
        try:
            if not _ISO_DAY.fullmatch(key):
                raise ValueError(key)
            day = date.fromisoformat(key)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Data inválida '{key}': use o formato ISO YYYY-MM-DD (ex.: 2026-11-03)."
            ) from exc

        if day > today:
            raise ValueError(
                f"Data '{key}' está no futuro (hoje é {today.isoformat()}); "
                "informe a data de publicação da notícia."
            )

        return day

    @staticmethod
    def _normalize_links(key: str, value: object) -> List[_Link]:
        """Valida a lista de uma data e devolve ``(url, horário)`` sem URLs repetidas.

        Em URL repetida na mesma data vale a primeira ocorrência, que herda o
        horário da repetição quando ela mesma não tinha um.
        """
        if not isinstance(value, list):
            raise ValueError(
                f"Os links da data '{key}' devem ser uma lista de URLs; "
                f"recebido: {type(value).__name__}."
            )

        links: List[_Link] = []
        for item in value:
            url, when = NewsLinksByDate._parse_item(key, item)
            NewsLinksByDate._merge_item(links, url, when)

        return links

    @staticmethod
    def _merge_item(links: List[_Link], url: str, when: Optional[time]) -> None:
        """Acrescenta o item, colapsando repetição de URL e preservando o horário conhecido."""
        for index, (existing_url, existing_time) in enumerate(links):
            if existing_url != url:
                continue

            if existing_time is None and when is not None:
                links[index] = (existing_url, when)
            return

        links.append((url, when))

    @staticmethod
    def _parse_item(key: str, item: object) -> _Link:
        """Aceita string (horário desconhecido) ou objeto ``{"url", "time"?}``."""
        if isinstance(item, dict):
            return NewsLinksByDate._parse_object_item(key, item)

        return NewsLinksByDate._clean_url(key, item), None

    @staticmethod
    def _parse_object_item(key: str, item: dict) -> _Link:
        """Valida um item-objeto: ``url`` obrigatório, ``time`` opcional, sem outras chaves."""
        unknown = sorted(str(k) for k in item if k not in _OBJECT_KEYS)
        if unknown:
            raise ValueError(
                f"Item inválido na data '{key}': chave(s) desconhecida(s) {unknown}; "
                'use apenas "url" e "time".'
            )

        if "url" not in item:
            raise ValueError(
                f"Item inválido na data '{key}': o campo \"url\" é obrigatório."
            )

        url = NewsLinksByDate._clean_url(key, item["url"])
        when = NewsLinksByDate._parse_time(key, url, item.get("time"))
        return url, when

    @staticmethod
    def _parse_time(key: str, url: str, raw: object) -> Optional[time]:
        """Valida ``HH:MM`` (24h); None/ausente significa horário desconhecido."""
        if raw is None:
            return None

        if not isinstance(raw, str) or not _HH_MM.fullmatch(raw.strip()):
            raise ValueError(
                f"Horário inválido '{raw}' na data '{key}' (URL {url}): "
                "use o formato HH:MM, 24h, horário de Brasília (ex.: 18:42)."
            )

        hours, minutes = (int(part) for part in raw.strip().split(":"))
        if hours > 23 or minutes > 59:
            raise ValueError(
                f"Horário inválido '{raw}' na data '{key}' (URL {url}): "
                "horas devem estar entre 00 e 23 e minutos entre 00 e 59."
            )

        return time(hours, minutes)

    @staticmethod
    def _clean_url(key: str, item: object) -> str:
        """Garante que o item é uma string não vazia e a apara."""
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"Item inválido na data '{key}': cada link deve ser uma string "
                f"não vazia; recebido: {item!r}."
            )

        return item.strip()

    @staticmethod
    def _register_links(
        groups: Dict[date, List[List[object]]],
        owner_by_url: Dict[str, date],
        day: date,
        links: List[_Link],
    ) -> None:
        """Associa os links à data, recusando URL já presente em outra data."""
        bucket = groups.setdefault(day, [])
        known = {entry[0]: entry for entry in bucket}

        for url, when in links:
            owner = owner_by_url.setdefault(url, day)
            if owner != day:
                raise ValueError(
                    f"A URL '{url}' aparece em mais de uma data "
                    f"({owner.isoformat()} e {day.isoformat()}); "
                    "uma notícia só pode ter uma data de publicação."
                )

            if url in known:
                if known[url][1] is None and when is not None:
                    known[url][1] = when
                continue

            entry = [url, when]
            known[url] = entry
            bucket.append(entry)
