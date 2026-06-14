"""ApiLlmAdapter — tratamento via Pydantic AI multiprovider."""

from typing import Optional

from src.ports.llm import LlmPort


class ApiLlmAdapter(LlmPort):
    """Chama uma LLM na nuvem via Pydantic AI; provider/modelo vêm de configuração.

    O `Agent` é construído preguiçosamente para não exigir credenciais no import.
    Nos testes injeta-se um `Agent` com `TestModel` (sem rede) para evitar chamadas reais.
    """

    def __init__(self, provider: str, model: str, *, agent: Optional[object] = None):
        """Initialize with the cloud provider/model, or an injected agent (tests)."""
        self._provider = provider
        self._model = model
        self._agent = agent

    def treat_news(self, markdown: str, *, prompt: str) -> str:
        """Send prompt + markdown to the model and return the cleaned text (Rule 1)."""
        agent = self._ensure_agent()
        result = agent.run_sync(f"{prompt}\n\n---\n\n{markdown}")
        return result.data

    def _ensure_agent(self):
        """Build (once) the Pydantic AI agent for the configured provider (Rule 1)."""
        if self._agent is not None:
            return self._agent

        from pydantic_ai import Agent

        self._agent = Agent(f"{self._provider}:{self._model}", result_type=str)
        return self._agent
