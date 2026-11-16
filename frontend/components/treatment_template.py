"""Templates de exemplo e texto inicial do editor de tratamento (sem Streamlit).

Os exemplos (`TEMPLATE_ORIGINAL`/`TEMPLATE_TRATADO`) servem só de **ilustração** do formato
esperado. Eles nunca devem virar conteúdo de uma notícia real: o editor de um link parte do
original convertido ou de um esqueleto vazio (`skeleton`), e `is_example` barra o salvamento
do exemplo.
"""

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


def is_example(text: str) -> bool:
    """Indica se o texto é o exemplo de template (não pode ser salvo como notícia)."""
    return text.strip() == TEMPLATE_TRATADO.strip()
