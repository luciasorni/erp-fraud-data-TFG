"""Construcción de índice KB en Chroma (RF15e-05)."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .kb_chroma import ensure_kb_collections, init_kb_chroma_client, load_kb_chroma_config
from .kb_chunking import chunk_extracted_documents, load_kb_chunking_config
from .kb_sources import load_kb_sources_config, resolve_kb_sources
from .kb_text_extractor import ExtractedTextDocument, extract_text_from_path


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _utc_timestamp_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash_embedding(text: str, *, dim: int = 128) -> list[float]:
    """Embedding determinista local para PoC (sin dependencias externas)."""
    if dim <= 0:
        raise ValueError("dim debe ser > 0")
    vector = [0.0] * dim
    words = text.lower().split()
    if not words:
        return vector

    for word in words:
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        slot = int.from_bytes(digest[:4], "big") % dim
        weight = ((digest[4] / 255.0) * 2.0) - 1.0
        vector[slot] += weight

    norm = sum(v * v for v in vector) ** 0.5
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


def _doc_type_from_path(path: str | Path) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix if suffix else "unknown"


def _build_doc_from_file(*, source_id: str, file_path: Path) -> list[ExtractedTextDocument]:
    docs = extract_text_from_path(source_id=source_id, path=file_path)
    file_hash = _sha256_file(file_path)
    out: list[ExtractedTextDocument] = []
    for doc in docs:
        merged_meta = dict(doc.metadata)
        merged_meta["source_file_hash"] = file_hash
        merged_meta["source_file_size"] = file_path.stat().st_size
        out.append(
            ExtractedTextDocument(
                source_id=doc.source_id,
                source_path=doc.source_path,
                doc_type=doc.doc_type,
                section_id=doc.section_id,
                text=doc.text,
                text_hash=doc.text_hash,
                metadata=merged_meta,
            )
        )
    return out


def _load_index_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"indexed_files": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"indexed_files": {}}
    indexed = payload.get("indexed_files", {})
    if not isinstance(indexed, dict):
        indexed = {}
    return {"indexed_files": {str(k): str(v) for k, v in indexed.items()}}


def _write_index_state(
    *,
    path: Path,
    indexed_files: dict[str, str],
) -> None:
    payload = {
        "version": "1.0.0",
        "updated_at_utc": _utc_timestamp_iso(),
        "indexed_files": dict(sorted(indexed_files.items())),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_kb_index(
    *,
    kb_sources_config_path: str | Path = "config/kb_sources.yaml",
    kb_chunking_config_path: str | Path = "config/kb_chunking.yaml",
    kb_chroma_config_path: str | Path = "config/kb_chroma.yaml",
    base_dir: str | Path = ".",
    output_manifest_path: str | Path = "kb/index_manifest.json",
    index_state_path: str | Path = "kb/index_state.json",
    include_optional_sources: bool = True,
    incremental_rebuild: bool = True,
) -> dict[str, Any]:
    """Construye/actualiza índice en Chroma y devuelve resumen."""
    sources_cfg = load_kb_sources_config(kb_sources_config_path)
    resolved = resolve_kb_sources(
        config_payload=sources_cfg,
        base_dir=base_dir,
        include_disabled=False,
    )

    missing_required = resolved["missing_required_source_ids"]
    if missing_required:
        raise ValueError(f"No se puede construir índice KB; faltan fuentes requeridas: {missing_required}")

    chunk_cfg = load_kb_chunking_config(kb_chunking_config_path)
    chroma_cfg = load_kb_chroma_config(kb_chroma_config_path)
    client, persist_dir = init_kb_chroma_client(config_payload=chroma_cfg, base_dir=base_dir)

    state_path = Path(index_state_path)
    previous_state = _load_index_state(state_path) if incremental_rebuild else {"indexed_files": {}}
    previous_hashes: dict[str, str] = dict(previous_state.get("indexed_files", {}))
    next_hashes: dict[str, str] = {}

    docs: list[ExtractedTextDocument] = []
    sources_used: list[dict[str, Any]] = []
    sources_skipped: list[dict[str, Any]] = []

    for source in resolved["resolved_sources"]:
        if not include_optional_sources and not bool(source.get("required", False)):
            continue
        if source.get("status") != "FOUND":
            continue
        source_id = str(source.get("source_id", ""))
        matched_files = source.get("matched_files", [])
        if not isinstance(matched_files, list):
            continue
        for matched in matched_files:
            file_path = Path(str(matched))
            file_hash = _sha256_file(file_path)
            file_key = str(file_path)
            next_hashes[file_key] = file_hash

            if incremental_rebuild and previous_hashes.get(file_key) == file_hash:
                sources_skipped.append(
                    {
                        "source_id": source_id,
                        "path": file_key,
                        "reason": "unchanged_hash",
                        "source_file_hash": file_hash,
                    }
                )
                continue

            extracted = _build_doc_from_file(source_id=source_id, file_path=file_path)
            docs.extend(extracted)
            sources_used.append(
                {
                    "source_id": source_id,
                    "path": file_key,
                    "doc_type": _doc_type_from_path(file_path),
                    "source_file_hash": file_hash,
                    "sections_extracted": len(extracted),
                }
            )

    chunks = chunk_extracted_documents(documents=docs, strategy_payload=chunk_cfg)

    collections: dict[str, str] = {}
    upserts_by_collection: dict[str, int] = {}
    if chunks:
        doc_types = sorted({_doc_type_from_path(chunk.source_path) for chunk in chunks})
        collections = ensure_kb_collections(
            client=client,
            config_payload=chroma_cfg,
            doc_types=doc_types,
        )

        for chunk in chunks:
            doc_type = _doc_type_from_path(chunk.source_path)
            collection_name = collections.get(doc_type)
            if not collection_name:
                continue
            col = client.get_collection(collection_name)
            metadata = dict(chunk.metadata)
            metadata["chunk_id"] = chunk.chunk_id
            metadata["source_id"] = chunk.source_id
            metadata["source_path"] = chunk.source_path
            metadata["doc_type"] = doc_type
            metadata["text_hash"] = chunk.text_hash
            col.upsert(
                ids=[chunk.chunk_id],
                documents=[chunk.text],
                metadatas=[metadata],
                embeddings=[_hash_embedding(chunk.text)],
            )
            upserts_by_collection[collection_name] = upserts_by_collection.get(collection_name, 0) + 1

    manifest = {
        "version": "1.0.0",
        "built_at_utc": _utc_timestamp_iso(),
        "persist_dir": str(persist_dir),
        "sources_used": sources_used,
        "sources_skipped": sources_skipped,
        "documents_extracted": len(docs),
        "chunks_indexed": len(chunks),
        "collections": collections,
        "upserts_by_collection": upserts_by_collection,
        "incremental_rebuild": bool(incremental_rebuild),
        "indexed_files_count": len(next_hashes),
        "chunking_config": chunk_cfg,
    }

    output_path = Path(output_manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_index_state(path=state_path, indexed_files=next_hashes)
    return manifest


def build_kb_index_manifest_row(manifest: dict[str, Any]) -> dict[str, Any]:
    """Resumen compacto serializable del build."""
    return {
        "chunks_indexed": int(manifest.get("chunks_indexed", 0)),
        "documents_extracted": int(manifest.get("documents_extracted", 0)),
        "collections_count": len(manifest.get("collections", {})),
        "sources_count": len(manifest.get("sources_used", [])),
        "persist_dir": str(manifest.get("persist_dir", "")),
    }
