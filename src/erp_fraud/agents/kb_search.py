"""KBSearchTool para consultar chunks indexados en Chroma (RF15e-07)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .kb_chroma import ensure_kb_collections, init_kb_chroma_client, load_kb_chroma_config


def _hash_embedding(text: str, *, dim: int = 128) -> list[float]:
    """Embedding determinista local para consulta KB."""
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


def _matches_filters(metadata: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        if metadata.get(key) != expected:
            return False
    return True


class KBSearchTool:
    """Tool de búsqueda semántica sobre índice KB en Chroma."""

    def __init__(
        self,
        *,
        kb_chroma_config_path: str | Path = "config/kb_chroma.yaml",
        base_dir: str | Path = ".",
    ) -> None:
        self.kb_chroma_config_path = Path(kb_chroma_config_path)
        self.base_dir = Path(base_dir)
        self._config = load_kb_chroma_config(self.kb_chroma_config_path)
        self._client, self._persist_dir = init_kb_chroma_client(
            config_payload=self._config,
            base_dir=self.base_dir,
        )
        doc_types = self._config.get("chroma", {}).get("default_doc_types", [])
        self._collections = ensure_kb_collections(
            client=self._client,
            config_payload=self._config,
            doc_types=doc_types,
        )

    @property
    def persist_dir(self) -> Path:
        return self._persist_dir

    def search(
        self,
        *,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(query, str) or len(query.strip()) < 3:
            raise ValueError("query debe ser string con al menos 3 caracteres")
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k debe ser entero > 0")

        query_clean = query.strip()
        query_embedding = _hash_embedding(query_clean)
        per_collection_k = max(top_k, 1)
        hits: list[dict[str, Any]] = []

        for collection_name in self._collections.values():
            col = self._client.get_collection(collection_name)
            result = col.query(
                query_embeddings=[query_embedding],
                n_results=per_collection_k,
                include=["documents", "metadatas", "distances"],
            )

            docs = (result.get("documents") or [[]])[0]
            metadatas = (result.get("metadatas") or [[]])[0]
            distances = (result.get("distances") or [[]])[0]
            ids = (result.get("ids") or [[]])[0]

            for idx, text in enumerate(docs):
                metadata = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
                if not _matches_filters(metadata, filters):
                    continue
                distance = float(distances[idx]) if idx < len(distances) else 0.0
                score = 1.0 / (1.0 + max(distance, 0.0))
                chunk_id = str(ids[idx]) if idx < len(ids) else str(metadata.get("chunk_id", ""))
                hits.append(
                    {
                        "chunk_id": chunk_id,
                        "text": str(text),
                        "score": score,
                        "distance": distance,
                        "metadata": metadata,
                        "collection": collection_name,
                    }
                )

        hits.sort(key=lambda item: (-float(item.get("score", 0.0)), str(item.get("chunk_id", ""))))
        return {
            "query": query_clean,
            "top_k": top_k,
            "filters": filters or {},
            "persist_dir": str(self._persist_dir),
            "count": min(top_k, len(hits)),
            "hits": hits[:top_k],
        }
