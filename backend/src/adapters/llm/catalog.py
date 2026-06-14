"""Catálogo de modelos locais e detecção de status em disco."""

from pathlib import Path
from typing import Dict, Iterable, List, Optional

# Estados possíveis de um modelo no disco (a UI mapeia para emoji + texto).
STATUS_READY = "ready"            # presente em llm-models/ → ✅ pronto para uso
STATUS_DOWNLOAD = "download"      # ainda não baixado       → ⬇️ download
STATUS_DOWNLOADING = "downloading"  # download em andamento → 🔁 fazendo download


def resolve_local_dir(models_dir: str, path: str) -> Path:
    """Resolve a pasta local de um modelo, sem duplicar o nome da pasta base."""
    p = Path(path)

    if p.is_absolute():
        return p

    base = Path(models_dir)
    if p.parts and p.parts[0] == base.name:
        return base.parent / p

    return base / p


def disk_status(models_dir: str, path: str, in_progress: Iterable[str]) -> str:
    """Determine the on-disk status of a single model."""
    if path in set(in_progress):
        return STATUS_DOWNLOADING

    local_dir = resolve_local_dir(models_dir, path)
    if _has_content(local_dir):
        return STATUS_READY

    return STATUS_DOWNLOAD


def list_with_status(
    models: List[Dict[str, str]],
    models_dir: str,
    in_progress: Iterable[str],
) -> List[Dict[str, str]]:
    """Append the on-disk status to each catalog entry."""
    in_progress = set(in_progress)
    enriched = []

    for model in models:
        path = str(model.get("path", ""))
        entry = dict(model)
        entry["status"] = disk_status(models_dir, path, in_progress)
        enriched.append(entry)

    return enriched


def find_by_path(models: List[Dict[str, str]], path: str) -> Optional[Dict[str, str]]:
    """Return the catalog entry whose `path` matches, or None."""
    for model in models:
        if str(model.get("path", "")) == path:
            return model

    return None


def repo_id_for(model: Dict[str, str]) -> str:
    """Resolve the HuggingFace repo id: explicit `repo`, else the path basename."""
    repo = model.get("repo")
    if repo:
        return str(repo)

    return Path(str(model.get("path", ""))).name


def _has_content(local_dir: Path) -> bool:
    """Return True when the model directory exists and holds at least one file."""
    if not local_dir.is_dir():
        return False

    return any(local_dir.iterdir())
