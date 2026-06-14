"""TreatedNewsRecord - documento de notícia tratado (tabela PIPELINE_TREATED_NEWS)."""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

_FENCE = "---"
_FRONTMATTER_KEYS = ("title", "subtitle", "url", "date", "category")


def parse_frontmatter(markdown: str) -> Tuple[Dict[str, str], str]:
    """Separa o frontmatter YAML simples do corpo.

    Returns:
        (metadata, body) — metadata sempre contém title/subtitle/url/date
        (string vazia quando ausente); body é o conteúdo após o frontmatter.
    """
    meta = {key: "" for key in _FRONTMATTER_KEYS}
    text = markdown.lstrip()

    if not text.startswith(_FENCE):
        return meta, markdown.strip()

    lines = text.splitlines()
    closing = _find_closing_fence(lines)

    if closing is None:
        return meta, markdown.strip()

    for line in lines[1:closing]:
        _absorb_frontmatter_line(line, meta)

    body = "\n".join(lines[closing + 1:]).strip()
    return meta, body


def _find_closing_fence(lines) -> Optional[int]:
    """Index of the closing `---` fence, or None when absent."""
    for index in range(1, len(lines)):
        if lines[index].strip() == _FENCE:
            return index

    return None


def _absorb_frontmatter_line(line: str, meta: Dict[str, str]) -> None:
    """Parse one `key: value` frontmatter line into the metadata dict."""
    if ":" not in line:
        return

    key, _, value = line.partition(":")
    key = key.strip().lower()

    if key in meta:
        meta[key] = value.strip()


@dataclass(frozen=True)
class TreatedNewsRecord:
    """Notícia tratada: frontmatter (title/subtitle/url/date/category) + conteúdo."""

    url: str                       # link da notícia (PK)
    title: str
    subtitle: str
    date: str                      # data da matéria (DD-MM-AAAA), como texto
    content: str                   # markdown tratado completo (frontmatter + corpo)
    category: str = ""             # uma das categorias de NewsCategory
    proc_id: Optional[str] = None  # uuid da execução associada

    @classmethod
    def from_treated_markdown(
        cls,
        url: str,
        treated_markdown: str,
        proc_id: Optional[str] = None,
    ) -> "TreatedNewsRecord":
        """Build a record by parsing the frontmatter of the treated markdown."""
        meta, _ = parse_frontmatter(treated_markdown)
        return cls(
            url=url,
            title=meta["title"],
            subtitle=meta["subtitle"],
            date=meta["date"],
            category=meta.get("category", ""),
            content=treated_markdown,
            proc_id=proc_id,
        )

    def to_dict(self) -> Dict[str, object]:
        """Serializa no formato das colunas da tabela."""
        return {
            "URL": self.url,
            "PROC_ID": self.proc_id,
            "TITLE": self.title,
            "SUBTITLE": self.subtitle,
            "NEWS_DATE": self.date,
            "CATEGORY": self.category,
            "CONTENT": self.content,
        }

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "TreatedNewsRecord":
        """Reconstrói o registro a partir de uma linha da tabela."""
        proc_id = row.get("PROC_ID")
        return cls(
            url=str(row["URL"]),
            title=str(row["TITLE"]) if row["TITLE"] is not None else "",
            subtitle=str(row["SUBTITLE"]) if row["SUBTITLE"] is not None else "",
            date=str(row["NEWS_DATE"]) if row["NEWS_DATE"] is not None else "",
            category=str(row.get("CATEGORY") or ""),
            content=str(row["CONTENT"]) if row["CONTENT"] is not None else "",
            proc_id=str(proc_id) if proc_id is not None else None,
        )
