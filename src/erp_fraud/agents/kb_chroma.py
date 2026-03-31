"""Inicialización de ChromaDB persistente y colecciones KB (RF15e-04)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .kb_chunking import KBChunk


class KBChromaConfigError(ValueError):
    """Error de configuración de Chroma KB."""


def load_kb_chroma_config(path: str | Path = "config/kb_chroma.yaml") -> dict[str, Any]:
    """Carga configuración de persistencia y colecciones Chroma."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"No existe config Chroma KB: {resolved}")
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("No se puede leer YAML sin PyYAML instalado") from exc

    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise KBChromaConfigError("kb_chroma.yaml debe contener objeto raíz")

    chroma = payload.get("chroma")
    if not isinstance(chroma, dict):
        raise KBChromaConfigError("kb_chroma.yaml: falta objeto 'chroma'")

    persist_directory = chroma.get("persist_directory")
    collection_prefix = chroma.get("collection_prefix")
    default_doc_types = chroma.get("default_doc_types")

    if not isinstance(persist_directory, str) or not persist_directory.strip():
        raise KBChromaConfigError("kb_chroma.yaml: 'persist_directory' inválido")
    if not isinstance(collection_prefix, str) or not collection_prefix.strip():
        raise KBChromaConfigError("kb_chroma.yaml: 'collection_prefix' inválido")
    if not isinstance(default_doc_types, list) or not default_doc_types:
        raise KBChromaConfigError("kb_chroma.yaml: 'default_doc_types' debe ser lista no vacía")

    for idx, doc_type in enumerate(default_doc_types):
        if not isinstance(doc_type, str) or not doc_type.strip():
            raise KBChromaConfigError(
                f"kb_chroma.yaml: default_doc_types[{idx}] debe ser string no vacío"
            )

    return payload


def _import_chromadb() -> Any:
    try:
        import chromadb  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Falta dependencia chromadb para usar KB vector store") from exc
    return chromadb


def init_kb_chroma_client(
    *,
    config_payload: dict[str, Any],
    base_dir: str | Path = ".",
) -> tuple[Any, Path]:
    """Inicializa cliente Chroma persistente."""
    chroma_cfg = config_payload.get("chroma", {})
    persist_rel = str(chroma_cfg.get("persist_directory", "")).strip()
    if not persist_rel:
        raise KBChromaConfigError("config_payload.chroma.persist_directory inválido")

    persist_dir = Path(base_dir) / persist_rel
    persist_dir.mkdir(parents=True, exist_ok=True)

    chromadb = _import_chromadb()
    client = chromadb.PersistentClient(path=str(persist_dir))
    return client, persist_dir


def _collection_name(prefix: str, doc_type: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in doc_type.strip().lower())
    return f"{prefix}_{normalized}"


def ensure_kb_collections(
    *,
    client: Any,
    config_payload: dict[str, Any],
    doc_types: Iterable[str] | None = None,
) -> dict[str, str]:
    """Crea/asegura colecciones por tipo de documento."""
    chroma_cfg = config_payload.get("chroma", {})
    prefix = str(chroma_cfg.get("collection_prefix", "kb")).strip()
    configured_doc_types = chroma_cfg.get("default_doc_types", [])
    if doc_types is None:
        doc_types_iter = configured_doc_types
    else:
        doc_types_iter = list(doc_types)

    if not isinstance(doc_types_iter, list) or not doc_types_iter:
        raise KBChromaConfigError("No hay doc_types para crear colecciones Chroma")

    out: dict[str, str] = {}
    for doc_type in doc_types_iter:
        if not isinstance(doc_type, str) or not doc_type.strip():
            continue
        name = _collection_name(prefix, doc_type)
        client.get_or_create_collection(name=name)
        out[doc_type.strip().lower()] = name
    return out


def infer_doc_types_from_chunks(chunks: Iterable[KBChunk]) -> list[str]:
    """Infiere doc_type desde source_path de chunks."""
    out: set[str] = set()
    for chunk in chunks:
        suffix = Path(chunk.source_path).suffix.lower().lstrip(".")
        if suffix:
            out.add(suffix)
    return sorted(out)
