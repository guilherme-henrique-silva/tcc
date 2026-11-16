"""Templates de exemplo e texto inicial do editor de tratamento (sem Streamlit).

Os exemplos (`TEMPLATE_ORIGINAL`/`TEMPLATE_TRATADO`) servem só de **ilustração** do formato
esperado. Eles nunca devem virar conteúdo de uma notícia real: o editor de um link parte do
original convertido ou de um esqueleto vazio (`skeleton`), e `is_example` barra o salvamento
do exemplo.
"""

import re
import unicodedata
from typing import Optional

# Exemplo de saída BRUTA do Docling (sem frontmatter — coluna esquerda "original")
TEMPLATE_ORIGINAL = """\
# Banco do Brasil fora do ar? Aplicativo tem instabilidade e clientes reclamam nas redes

## Segundo o site DownDetector, que monitora interrupções em serviços online, aplicativo chegou a ter mais de 2,5 mil pela manhã. Banco normalizou os serviços por volta das 15h20.

Por [Redação g1](https://g1.globo.com/autores/redacao-g1/) - São Paulo

10/06/2026 11h44 Atualizado 10/06/2026

Agência do Banco do Brasil de Caruaru, no Agreste de Pernambuco - Foto: Reprodução/Google Street View

O aplicativo do Banco do Brasil passou por instabilidade nesta quarta-feira (10). Nas redes \
sociais, clientes relataram problemas em acessar a conta e fazer transferências.

...\
"""

# Exemplo de notícia JÁ TRATADA (com frontmatter — exibido na página sem links)
TEMPLATE_TRATADO = """\
---
title: Banco do Brasil fora do ar? Aplicativo tem instabilidade e clientes reclamam nas redes
subtitle: Segundo o site DownDetector, que monitora interrupções em serviços online, \
aplicativo chegou a ter mais de 2,5 mil pela manhã. Banco normalizou os serviços por volta das 15h20.
url: https://g1.globo.com/economia/noticia/2026/06/10/banco-do-brasil-fora-do-ar.ghtml
date: 10-06-2026
category: finanças
---

O aplicativo do Banco do Brasil passou por instabilidade nesta quarta-feira (10). \
Nas redes sociais, clientes relataram problemas em acessar a conta e fazer transferências.

...\
"""


def skeleton(url: str, date_br: str = "") -> str:
    """Frontmatter vazio para um link real, com `url` e `date` já preenchidos."""
    return (
        "---\n"
        "title: \n"
        "subtitle: \n"
        f"url: {url}\n"
        f"date: {date_br}\n"
        "category: \n"
        "---\n"
        "\n"
    )


def initial_text(
    url: str,
    date_br: str,
    treated: Optional[str],
    original: Optional[str],
) -> str:
    """Texto inicial do editor: tratado salvo, senão o original, senão um esqueleto vazio."""
    if treated:
        return treated

    if original:
        return original

    return skeleton(url, date_br)


_DEFAULT_CATEGORY = "finanças"

# Palavras-chave (minúsculas, sem exigir acento) por categoria — heurística simples e editável.
_CATEGORY_KEYWORDS = {
    "agronegócio": ["agro", "agronegocio", "agricultura", "soja", "milho", "safra", "pecuaria",
                    "boi", "cafe", "cana", "fertilizante", "rural"],
    "macroeconomia": ["selic", "inflacao", "ipca", "pib", "juros", "copom", "banco central",
                      "dolar", "cambio", "fiscal", "reservas", "desemprego", "deficit", "superavit"],
    "política": ["governo", "lula", "congresso", "senado", "camara", "eleicao", "ministro",
                 "stf", "presidente", "reforma", "partido"],
    "tecnologia": ["tecnologia", "inteligencia artificial", "ia", "software", "aplicativo",
                   "app", "nuvem", "cibernetico", "algoritmo", "startup"],
    "microeconomia": ["consumidor", "varejo", "empresa", "industria", "salario",
                      "preco", "setor", "demanda", "oferta"],
    "finanças": ["acao", "acoes", "bolsa", "ibovespa", "dividendo", "dividendos", "banco",
                 "fundo", "investimento", "investidor", "balanco", "lucro", "tesouro", "bbas3"],
}

_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_BR_DATE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


def _plain(text: str) -> str:
    """Texto de uma linha só: sem links/ênfase Markdown e com espaços colapsados."""
    text = _MD_LINK.sub(r"\1", text)
    text = text.replace("*", "").replace("`", "")
    return " ".join(text.split())


def _heading(lines: list, prefix: str) -> tuple:
    """(índice, texto) do primeiro título com o prefixo dado (`# `, `## `), ou (None, "")."""
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            return index, _plain(line[len(prefix):])

    return None, ""


def _fold(text: str) -> str:
    """Minúsculas sem acentos, para casar palavras-chave."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _keyword_hits(text: str, keywords: list) -> int:
    """Total de ocorrências (palavra inteira) das palavras-chave no texto."""
    return sum(len(re.findall(rf"\b{re.escape(word)}\b", text)) for word in keywords)


def guess_category(title: str, subtitle: str, body: str) -> str:
    """Categoria por palavras-chave (título/subtítulo pesam 3×); padrão: finanças."""
    head = _fold(f"{title} {subtitle}")
    rest = _fold(body)
    scores = {
        category: 3 * _keyword_hits(head, words) + _keyword_hits(rest, words)
        for category, words in _CATEGORY_KEYWORDS.items()
    }
    best = max(scores.values())

    if best == 0:
        return _DEFAULT_CATEGORY

    return next(category for category, score in scores.items() if score == best)


def article_date(original: str) -> str:
    """Primeira data `DD/MM/AAAA` do texto, como `DD-MM-AAAA` (vazio se não houver)."""
    match = _BR_DATE.search(original)

    if not match:
        return ""

    day, month, year = match.groups()
    return f"{day}-{month}-{year}"


def formatted(url: str, date_br: str, original: str) -> str:
    """Original do Docling com frontmatter completo (title/subtitle/url/date/category).

    `title`/`subtitle` vêm dos primeiros `#`/`##`, que saem do corpo; `date` é a data informada
    no upload, ou a primeira data do texto; `category` vem de `guess_category`.
    """
    lines = original.splitlines()
    title_at, title = _heading(lines, "# ")
    subtitle_at, subtitle = _heading(lines, "## ")
    dropped = {index for index in (title_at, subtitle_at) if index is not None}
    body = "\n".join(line for i, line in enumerate(lines) if i not in dropped).strip()

    return (
        "---\n"
        f"title: {title}\n"
        f"subtitle: {subtitle}\n"
        f"url: {url}\n"
        f"date: {date_br or article_date(original)}\n"
        f"category: {guess_category(title, subtitle, body)}\n"
        "---\n"
        "\n"
        f"{body}\n"
    )


def is_example(text: str) -> bool:
    """Indica se o texto é o exemplo de template (não pode ser salvo como notícia)."""
    return text.strip() == TEMPLATE_TRATADO.strip()
