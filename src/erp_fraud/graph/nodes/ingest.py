"""Nodos de ingest y KB index."""

from __future__ import annotations

# ruff: noqa: F401

from . import _legacy as _legacy

globals().update(vars(_legacy))

def ingest_node(state: GraphState) -> GraphState:
    """Nodo de ingesta no-LLM: carga `schema_summary` en el estado (RF14-03)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    schema_summary_path = str(metadata.get("schema_summary_path", "")).strip()
    db_path = _resolve_project_path(str(metadata.get("db_path", DEFAULT_DB_PATH)).strip() or DEFAULT_DB_PATH)
    schema_name = str(metadata.get("schema_name", DEFAULT_SCHEMA_NAME)).strip() or DEFAULT_SCHEMA_NAME

    if schema_summary_path:
        path = Path(_resolve_project_path(schema_summary_path))
        if not path.exists():
            raise FileNotFoundError(f"schema_summary_path no existe: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"schema_summary inválido en {path}")
        state.schema = payload
        metadata["ingest_source"] = "schema_summary_json"
        metadata["ingest_schema_summary_path"] = str(path)
        metadata["ingest_table_count"] = int(payload.get("table_count", 0) or 0)
        return state

    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"No existe db_path ({db_path}) ni schema_summary_path para ingest_node"
        )

    summary = build_schema_summary(db_path=db_path, schema_name=schema_name)
    state.schema = summary
    metadata["ingest_source"] = "duckdb"
    metadata["ingest_db_path"] = db_path
    metadata["ingest_schema_name"] = schema_name
    metadata["ingest_table_count"] = int(summary.get("table_count", 0) or 0)
    return state

def kb_index_node(state: GraphState) -> GraphState:
    """Nodo no-LLM: asegura índice KB (RF14-04) con rebuild incremental."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    enabled = bool(metadata.get("kb_index_enabled", DEFAULT_KB_ENABLED))
    if not enabled:
        state.kb_status = {
            "status": "DISABLED",
            "index_manifest_path": "",
            "chunks_indexed": 0,
            "sources_used": 0,
            "error": "",
            "incremental_rebuild": True,
        }
        metadata["kb_index_status"] = "DISABLED"
        return state

    base_dir = str(metadata.get("base_dir", DEFAULT_BASE_DIR)).strip() or DEFAULT_BASE_DIR
    kb_sources_config = str(metadata.get("kb_sources_config", DEFAULT_KB_SOURCES_CONFIG)).strip()
    kb_chunking_config = str(metadata.get("kb_chunking_config", DEFAULT_KB_CHUNKING_CONFIG)).strip()
    kb_chroma_config = str(metadata.get("kb_chroma_config", DEFAULT_KB_CHROMA_CONFIG)).strip()
    kb_manifest_path = str(metadata.get("kb_manifest_path", DEFAULT_KB_MANIFEST_PATH)).strip()
    kb_index_state_path = str(metadata.get("kb_index_state_path", DEFAULT_KB_STATE_PATH)).strip()

    try:
        manifest = build_kb_index(
            kb_sources_config_path=kb_sources_config,
            kb_chunking_config_path=kb_chunking_config,
            kb_chroma_config_path=kb_chroma_config,
            base_dir=base_dir,
            output_manifest_path=kb_manifest_path,
            index_state_path=kb_index_state_path,
            incremental_rebuild=True,
        )
    except Exception as exc:
        state.kb_status = {
            "status": "ERROR",
            "index_manifest_path": kb_manifest_path,
            "chunks_indexed": 0,
            "sources_used": 0,
            "error": f"{type(exc).__name__}: {exc}",
            "incremental_rebuild": True,
        }
        metadata["kb_index_status"] = "ERROR"
        raise

    state.kb_status = {
        "status": "OK",
        "index_manifest_path": kb_manifest_path,
        "chunks_indexed": int(manifest.get("chunks_indexed", 0) or 0),
        "sources_used": len(manifest.get("sources_used", [])),
        "error": "",
        "incremental_rebuild": True,
    }
    metadata["kb_index_status"] = "OK"
    metadata["kb_index_manifest_path"] = kb_manifest_path
    metadata["kb_index_state_path"] = kb_index_state_path
    return state
