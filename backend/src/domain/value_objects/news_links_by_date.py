"""NewsLinksByDate — value object imutável com os links de notícias agrupados por data."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from .date_range import DateRange

# date.fromisoformat (3.11+) aceita também AAAAMMDD e AAAA-Www-D; a spec exige YYYY-MM-DD.
_ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class NewsLinksByDate:
    """Coleção imutável *data de publicação → links* (first-class collection).

    Formato válido (chaves ISO ``YYYY-MM-DD``, valores são listas de links):

        {
          "2026-11-03": ["https://g1.globo.com/economia/noticia/a.ghtml",
                         "https://www.infomoney.com.br/mercados/b/"],
          "2026-11-04": ["https://g1.globo.com/economia/noticia/c.ghtml"]
        }

    Construa sempre via ``from_raw``, que valida e normaliza. Formatos legados
    (lista plana, ``{"links": [...]}`` ou string que não é JSON) são rejeitados.
    """

    _groups: Tuple[Tuple[date, Tuple[str, ...]], ...] = ()

    @classmethod
    def from_raw(cls, raw: object, today: Optional[date] = None) -> "NewsLinksByDate":
        """Valida ``raw`` (dict ou string JSON) e devolve a coleção normalizada.

        ``None``, string em branco e ``{}`` geram coleção vazia. Violações geram
        ``ValueError`` com mensagem em PT-BR identificando a chave ou URL ofensora.
        """
        payload = cls._load_payload(raw)
        limit = today or date.today()

        groups: Dict[date, List[str]] = {}
        owner_by_url: Dict[str, date] = {}

        for key, value in payload.items():
            day = cls._parse_day(key, limit)
            links = cls._normalize_links(key, value)
            cls._register_links(groups, owner_by_url, day, links)

        ordered = tuple(
            (day, tuple(links)) for day, links in sorted(groups.items()) if links
        )
        return cls(ordered)

    def items(self) -> List[Tuple[str, date]]:
        """Pares ``(url, data)`` por data crescente e, na data, na ordem informada."""
        return [(url, day) for day, links in self._groups for url in links]

    def urls(self) -> List[str]:
        """URLs na mesma ordem de ``items()``."""
        return [url for url, _ in self.items()]

    def dates_outside(self, date_range: DateRange) -> List[date]:
        """Datas fora do período de análise (apenas para avisos; não invalida)."""
        return [day for day, _ in self._groups if not date_range.contains(day)]

    def to_dict(self) -> Dict[str, List[str]]:
        """Serializa com chaves ISO (útil para logs, checkpoints e a API)."""
        return {day.isoformat(): list(links) for day, links in self._groups}

    def is_empty(self) -> bool:
        """Indica se não há nenhuma URL."""
        return len(self) == 0

    def __len__(self) -> int:
        return sum(len(links) for _, links in self._groups)

    # ------------------------------------------------------------------ #
    # Parsing e validação                                                 #
    # ------------------------------------------------------------------ #
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
    def _normalize_links(key: str, value: object) -> List[str]:
        """Valida a lista de uma data e devolve as URLs aparadas, sem repetidas."""
        if not isinstance(value, list):
            raise ValueError(
                f"Os links da data '{key}' devem ser uma lista de URLs; "
                f"recebido: {type(value).__name__}."
            )

        links: List[str] = []
        for item in value:
            url = NewsLinksByDate._clean_url(key, item)
            if url not in links:
                links.append(url)

        return links

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
        groups: Dict[date, List[str]],
        owner_by_url: Dict[str, date],
        day: date,
        links: List[str],
    ) -> None:
        """Associa os links à data, recusando URL já presente em outra data."""
        bucket = groups.setdefault(day, [])

        for url in links:
            owner = owner_by_url.setdefault(url, day)
            if owner != day:
                raise ValueError(
                    f"A URL '{url}' aparece em mais de uma data "
                    f"({owner.isoformat()} e {day.isoformat()}); "
                    "uma notícia só pode ter uma data de publicação."
                )
            bucket.append(url)
