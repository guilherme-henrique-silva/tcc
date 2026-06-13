"""LLM adapters - implementações do LlmPort (local HF e API via Pydantic AI)."""

from .local_llm_adapter import LocalLlmAdapter
from .api_llm_adapter import ApiLlmAdapter
from .prompts import _PROMPT_TRATAMENTO_NOTICIAS
from .catalog import (
    list_with_status,
    disk_status,
    resolve_local_dir,
    STATUS_READY,
    STATUS_DOWNLOAD,
    STATUS_DOWNLOADING,
)

PROMPT_TRATAMENTO_NOTICIAS = _PROMPT_TRATAMENTO_NOTICIAS

__all__ = [
    "LocalLlmAdapter",
    "ApiLlmAdapter",
    "PROMPT_TRATAMENTO_NOTICIAS",
    "list_with_status",
    "disk_status",
    "resolve_local_dir",
    "STATUS_READY",
    "STATUS_DOWNLOAD",
    "STATUS_DOWNLOADING",
]
