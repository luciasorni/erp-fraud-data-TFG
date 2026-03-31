from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from src.erp_fraud.agents.kb_index import ExtractedTextDocument, build_kb_index
from src.erp_fraud.agents.kb_search import KBSearchTool, _hash_embedding


@dataclass
class _FakeChunk:
    source_id: str
    source_path: str
    section_id: str
    chunk_id: str
    chunk_index: int
    text: str
    text_hash: str
    metadata: dict[str, Any]


class _FakeCollection:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> None:
        for idx, item_id in enumerate(ids):
            self.store[item_id] = {
                "id": item_id,
                "document": documents[idx],
                "metadata": metadatas[idx],
                "embedding": embeddings[idx],
            }

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int,
        include: list[str],
    ) -> dict[str, list[list[Any]]]:
        _ = include
        query = query_embeddings[0]
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in self.store.values():
            emb = row["embedding"]
            distance = sum((a - b) ** 2 for a, b in zip(query, emb))
            scored.append((distance, row))
        scored.sort(key=lambda x: (x[0], x[1]["id"]))
        top = scored[:n_results]
        return {
            "ids": [[item[1]["id"] for item in top]],
            "documents": [[item[1]["document"] for item in top]],
            "metadatas": [[item[1]["metadata"] for item in top]],
            "distances": [[item[0] for item in top]],
        }


class _FakeClient:
    def __init__(self) -> None:
        self.collections: dict[str, _FakeCollection] = {}

    def get_or_create_collection(self, name: str) -> _FakeCollection:
        if name not in self.collections:
            self.collections[name] = _FakeCollection()
        return self.collections[name]

    def get_collection(self, name: str) -> _FakeCollection:
        return self.get_or_create_collection(name)


def _patch_kb_index_dependencies(monkeypatch: Any, source_file: Path, fake_client: _FakeClient) -> None:
    import src.erp_fraud.agents.kb_index as kb_index

    monkeypatch.setattr(kb_index, "load_kb_sources_config", lambda *_a, **_k: {"sources": []})
    monkeypatch.setattr(
        kb_index,
        "resolve_kb_sources",
        lambda **_k: {
            "resolved_sources": [
                {
                    "source_id": "demo_doc",
                    "required": True,
                    "status": "FOUND",
                    "matched_files": [str(source_file)],
                }
            ],
            "missing_required_source_ids": [],
        },
    )
    monkeypatch.setattr(
        kb_index,
        "load_kb_chunking_config",
        lambda *_a, **_k: {
            "strategy": {"mode": "character_window", "chunk_size": 1000, "chunk_overlap": 50, "min_chunk_size": 1}
        },
    )
    monkeypatch.setattr(
        kb_index,
        "load_kb_chroma_config",
        lambda *_a, **_k: {
            "chroma": {"persist_directory": "kb/chroma_test", "collection_prefix": "kb", "default_doc_types": ["md"]}
        },
    )
    monkeypatch.setattr(kb_index, "init_kb_chroma_client", lambda **_k: (fake_client, Path("kb/chroma_test")))
    monkeypatch.setattr(kb_index, "ensure_kb_collections", lambda **_k: {"md": "kb_md"})

    def _build_doc_from_file(*, source_id: str, file_path: Path) -> list[ExtractedTextDocument]:
        text = file_path.read_text(encoding="utf-8")
        return [
            ExtractedTextDocument(
                source_id=source_id,
                source_path=str(file_path),
                doc_type="md",
                section_id="full",
                text=text,
                text_hash="text_hash",
                metadata={"source_file_hash": "file_hash"},
            )
        ]

    def _chunk_docs(*, documents: list[ExtractedTextDocument], strategy_payload: dict[str, Any]) -> list[_FakeChunk]:
        _ = strategy_payload
        chunks: list[_FakeChunk] = []
        for doc in documents:
            chunks.append(
                _FakeChunk(
                    source_id=doc.source_id,
                    source_path=doc.source_path,
                    section_id=doc.section_id,
                    chunk_id=f"{doc.source_id}:full:0001",
                    chunk_index=1,
                    text=doc.text,
                    text_hash="chunk_hash",
                    metadata={"source_id": doc.source_id, "source_path": doc.source_path, "doc_type": "md"},
                )
            )
        return chunks

    monkeypatch.setattr(kb_index, "_build_doc_from_file", _build_doc_from_file)
    monkeypatch.setattr(kb_index, "chunk_extracted_documents", _chunk_docs)


def test_rf15e08_build_rebuild_no_change_and_changed(monkeypatch: Any, tmp_path: Path) -> None:
    source_file = tmp_path / "doc.md"
    source_file.write_text("first content", encoding="utf-8")
    fake_client = _FakeClient()
    _patch_kb_index_dependencies(monkeypatch, source_file, fake_client)

    manifest_path = tmp_path / "index_manifest.json"
    state_path = tmp_path / "index_state.json"

    manifest_1 = build_kb_index(
        base_dir=tmp_path,
        output_manifest_path=manifest_path,
        index_state_path=state_path,
        incremental_rebuild=True,
    )
    assert manifest_1["chunks_indexed"] == 1
    assert len(manifest_1["sources_used"]) == 1
    assert manifest_1["sources_skipped"] == []

    manifest_2 = build_kb_index(
        base_dir=tmp_path,
        output_manifest_path=manifest_path,
        index_state_path=state_path,
        incremental_rebuild=True,
    )
    assert manifest_2["chunks_indexed"] == 0
    assert manifest_2["sources_used"] == []
    assert len(manifest_2["sources_skipped"]) == 1
    assert manifest_2["sources_skipped"][0]["reason"] == "unchanged_hash"

    source_file.write_text("first content + changed", encoding="utf-8")
    manifest_3 = build_kb_index(
        base_dir=tmp_path,
        output_manifest_path=manifest_path,
        index_state_path=state_path,
        incremental_rebuild=True,
    )
    assert manifest_3["chunks_indexed"] == 1
    assert len(manifest_3["sources_used"]) == 1
    assert manifest_3["sources_skipped"] == []

    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert "indexed_files" in state_payload
    assert str(source_file) in state_payload["indexed_files"]


def test_rf15e08_kb_search_returns_metadata(monkeypatch: Any) -> None:
    import src.erp_fraud.agents.kb_search as kb_search

    fake_client = _FakeClient()
    md_col = fake_client.get_or_create_collection("kb_md")
    md_col.upsert(
        ids=["chunk-1", "chunk-2"],
        documents=["duplicate invoice vendor high amount", "payment timing weekend"],
        metadatas=[
            {"source_id": "acfe_pdf", "source_path": "docs/external/a.pdf", "doc_type": "pdf"},
            {"source_id": "project_docs", "source_path": "docs/how_to_run.md", "doc_type": "md"},
        ],
        embeddings=[
            _hash_embedding("duplicate invoice vendor high amount"),
            _hash_embedding("payment timing weekend"),
        ],
    )

    monkeypatch.setattr(
        kb_search,
        "load_kb_chroma_config",
        lambda *_a, **_k: {
            "chroma": {"persist_directory": "kb/chroma_test", "collection_prefix": "kb", "default_doc_types": ["md"]}
        },
    )
    monkeypatch.setattr(kb_search, "init_kb_chroma_client", lambda **_k: (fake_client, Path("kb/chroma_test")))
    monkeypatch.setattr(kb_search, "ensure_kb_collections", lambda **_k: {"md": "kb_md"})

    tool = KBSearchTool(base_dir=".")
    out = tool.search(query="duplicate invoice", top_k=1, filters={"source_id": "acfe_pdf"})

    assert out["count"] == 1
    assert len(out["hits"]) == 1
    assert "score" in out["hits"][0]
    assert "metadata" in out["hits"][0]
    assert out["hits"][0]["metadata"]["source_id"] == "acfe_pdf"
