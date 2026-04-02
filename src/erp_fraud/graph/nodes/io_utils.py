"""Helpers de IO de nodos extraídos de `_legacy`."""

from __future__ import annotations

from pathlib import Path

from ...storage.paths import ruta_run
from .persist_utils import (
    collect_alphacodium_artifacts as _collect_alphacodium_artifacts,
    write_explanations_markdown as _write_explanations_markdown,
    write_json as _write_json,
)


write_json = _write_json
write_explanations_markdown = _write_explanations_markdown
collect_alphacodium_artifacts = _collect_alphacodium_artifacts


def run_dir_from_id(run_id: str) -> Path:
    return ruta_run(run_id)
