"""LlmPort — contrato hexagonal para tratamento de notícias via LLM."""

from abc import ABC, abstractmethod


class LlmPort(ABC):
    """Interface para adapters de LLM (local ou API), isolando o domínio do provedor."""

    @abstractmethod
    def treat_news(self, markdown: str, *, prompt: str) -> str:
        """Trata o Markdown de uma notícia segundo o prompt, retornando o texto limpo.

        Args:
            markdown: conteúdo bruto da notícia convertido pelo Docling.
            prompt: instrução de tratamento (excluir ruído, inserir frontmatter).

        Returns:
            Markdown tratado com frontmatter (title/subtitle/url/date) no topo.
        """
        pass
