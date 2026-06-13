"""Bloco de contexto de negócio reutilizável por página (Requisito 4 do spec)."""

import streamlit as st


def context_block(title: str, body: str) -> None:
    """Render a domain-context box at the top of a page (Requisito 4).

    Explica, sem pressupor conhecimento prévio, o que aquela tela faz no domínio
    de análise do impacto de notícias sobre o preço da ação (PLANO_DE_ACAO.md).
    """
    with st.container(border=True):
        st.markdown(f"#### ℹ️ {title}")
        st.markdown(body)
