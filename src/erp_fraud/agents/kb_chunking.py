"""Chunking de documentos KB con metadata trazable (RF15e-03)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .kb_text_extractor import ExtractedTextDocument


class KBChunkingConfigError(ValueError):
    """Error de configuración de estrategia de chunking."""


@dataclass(frozen=True)
class KBChunk:
    source_id: str
    source_path: str
    section_id: str
    chunk_id: str
    chunk_index: int
    text: str
    text_hash: str
    metadata: dict[str, object]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_kb_chunking_config(path: str | Path = "config/kb_chunking.yaml") -> dict[str, Any]:
    """Carga configuración de chunking."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"No existe config de chunking: {resolved}")
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("No se puede leer YAML sin PyYAML instalado") from exc

    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise KBChunkingConfigError("kb_chunking.yaml debe contener objeto raíz")

    strategy = payload.get("strategy")
    if not isinstance(strategy, dict):
        raise KBChunkingConfigError("kb_chunking.yaml: falta objeto 'strategy'")
    if strategy.get("mode") != "character_window":
        raise KBChunkingConfigError("kb_chunking.yaml: strategy.mode debe ser 'character_window'")

    for key in ("chunk_size", "chunk_overlap", "min_chunk_size"):
        value = strategy.get(key)
        if isinstance(value, bool):
            raise KBChunkingConfigError(f"kb_chunking.yaml: '{key}' inválido")
        try:
            parsed = int(value)
        except Exception as exc:
            raise KBChunkingConfigError(f"kb_chunking.yaml: '{key}' debe ser entero") from exc
        if parsed <= 0:
            raise KBChunkingConfigError(f"kb_chunking.yaml: '{key}' debe ser > 0")

    if int(strategy["chunk_overlap"]) >= int(strategy["chunk_size"]):
        raise KBChunkingConfigError("kb_chunking.yaml: chunk_overlap debe ser < chunk_size")

    return payload


def _chunk_text(
    *,
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_size: int,
) -> list[tuple[str, int, int]]:
    if not text:
        return []
    step = chunk_size - chunk_overlap
    chunks: list[tuple[str, int, int]] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(text_len, start + chunk_size)
        part = text[start:end].strip()
        if len(part) >= min_chunk_size or (start == 0 and end == text_len):
            chunks.append((part, start, end))
        if end >= text_len:
            break
        start += step
    return chunks


def chunk_extracted_documents(
    *,
    documents: Iterable[ExtractedTextDocument],
    strategy_payload: dict[str, Any],
) -> list[KBChunk]:
    """Genera chunks con metadata fuente/sección/hash."""
    strategy = strategy_payload.get("strategy", {})
    chunk_size = int(strategy["chunk_size"])
    chunk_overlap = int(strategy["chunk_overlap"])
    min_chunk_size = int(strategy["min_chunk_size"])

    out: list[KBChunk] = []
    for doc in documents:
        pieces = _chunk_text(
            text=doc.text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size,
        )
        for idx, (chunk_text, start, end) in enumerate(pieces, start=1):
            chunk_id = f"{doc.source_id}:{doc.section_id}:{idx:04d}"
            out.append(
                KBChunk(
                    source_id=doc.source_id,
                    source_path=doc.source_path,
                    section_id=doc.section_id,
                    chunk_id=chunk_id,
                    chunk_index=idx,
                    text=chunk_text,
                    text_hash=_sha256(chunk_text),
                    metadata={
                        "source": doc.source_path,
                        "section_id": doc.section_id,
                        "source_hash": doc.text_hash,
                        "chunk_start": start,
                        "chunk_end": end,
                        **doc.metadata,
                    },
                )
            )
    return out


def save_kb_chunks_jsonl(
    *,
    chunks: Iterable[KBChunk],
    output_path: str | Path,
) -> Path:
    """Persistencia de chunks para indexado posterior."""
    resolved = Path(output_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(asdict(chunk), ensure_ascii=False, sort_keys=True) + "\n")
    return resolved
