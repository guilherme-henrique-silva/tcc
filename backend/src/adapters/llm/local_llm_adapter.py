"""LocalLlmAdapter — tratamento via HuggingFace Transformers, CPU/GPU-aware."""

from typing import Callable, Optional

from src.ports.llm import LlmPort
from src.adapters.llm.catalog import resolve_local_dir, STATUS_READY, disk_status


class LocalLlmAdapter(LlmPort):
    """Carrega um modelo local de `llm-models/` e roda inferência sob demanda.

    Imports pesados (torch/transformers/huggingface_hub) são preguiçosos, e os
    colaboradores de download/geração são injetáveis para permitir testes sem
    baixar nem carregar pesos reais.
    """

    def __init__(
        self,
        model_path: str,
        models_dir: str,
        *,
        repo_id: Optional[str] = None,
        snapshot_download: Optional[Callable] = None,
        pipeline_builder: Optional[Callable] = None,
    ):
        """Initialize with the selected model path and the local cache directory."""
        self._model_path = model_path
        self._models_dir = models_dir
        self._repo_id_value = repo_id
        self._snapshot_download = snapshot_download
        self._pipeline_builder = pipeline_builder
        self._generator = None  # pipeline de text-generation (lazy)

    def treat_news(self, markdown: str, *, prompt: str) -> str:
        """Ensure the model is on disk, then run local inference (Rule 1: delegate)."""
        self._ensure_downloaded()
        generator = self._ensure_generator()

        composed = f"{prompt}\n\n---\n\n{markdown}"
        return self._generate(generator, composed)

    def _ensure_downloaded(self) -> None:
        """Download the selected model only when missing — never re-download."""
        if disk_status(self._models_dir, self._model_path, in_progress=()) == STATUS_READY:
            return

        download = self._snapshot_download or self._default_snapshot_download()
        local_dir = resolve_local_dir(self._models_dir, self._model_path)
        download(repo_id=self._repo_id(), local_dir=str(local_dir))

    def _ensure_generator(self):
        """Build (once) the text-generation pipeline, CPU/GPU-aware (Rule 1)."""
        if self._generator is not None:
            return self._generator

        builder = self._pipeline_builder or self._default_pipeline_builder()
        local_dir = resolve_local_dir(self._models_dir, self._model_path)
        self._generator = builder(str(local_dir), self._select_device())
        return self._generator

    def _generate(self, generator: Callable, text: str) -> str:
        """Run the generator and return only the produced text (Rule 1)."""
        outputs = generator(text)
        return self._extract_text(outputs)

    def _extract_text(self, outputs) -> str:
        """Normalize the transformers pipeline output into a string (Rule 1)."""
        if isinstance(outputs, list) and outputs:
            first = outputs[0]
            if isinstance(first, dict):
                return str(first.get("generated_text", "")).strip()
            return str(first).strip()

        return str(outputs).strip()

    def _repo_id(self) -> str:
        """Use the explicit repo id, else derive it from the model path (Rule 1)."""
        if self._repo_id_value:
            return self._repo_id_value

        return resolve_local_dir(self._models_dir, self._model_path).name

    def _select_device(self) -> int:
        """Return 0 for CUDA when available, else -1 for CPU."""
        import torch

        return 0 if torch.cuda.is_available() else -1

    def _default_snapshot_download(self) -> Callable:
        """Lazily resolve huggingface_hub.snapshot_download (Rule 1)."""
        from huggingface_hub import snapshot_download

        return snapshot_download

    def _default_pipeline_builder(self) -> Callable:
        """Lazily build a transformers text-generation pipeline factory (Rule 1)."""
        from transformers import pipeline

        def build(model_dir: str, device: int):
            return pipeline("text-generation", model=model_dir, device=device)

        return build
