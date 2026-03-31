"""Utilidades de control de políticas para flujo multiagente."""

try:
    from .alpha_loop import AlphaLoopResult, alpha_loop, alpha_loop_result_to_dict
except ModuleNotFoundError:  # pragma: no cover
    # Permite usar utilidades RF15b/RF15e sin dependencias de storage completas.
    AlphaLoopResult = None  # type: ignore[assignment]
    alpha_loop = None  # type: ignore[assignment]
    alpha_loop_result_to_dict = None  # type: ignore[assignment]
from .kb_sources import KBSourcesConfigError, load_kb_sources_config, resolve_kb_sources
from .kb_chunking import (
    KBChunk,
    KBChunkingConfigError,
    chunk_extracted_documents,
    load_kb_chunking_config,
    save_kb_chunks_jsonl,
)
from .kb_chroma import (
    KBChromaConfigError,
    ensure_kb_collections,
    infer_doc_types_from_chunks,
    init_kb_chroma_client,
    load_kb_chroma_config,
)
from .kb_index import build_kb_index, build_kb_index_manifest_row
from .kb_search import KBSearchTool
from .kb_text_extractor import (
    ExtractedTextDocument,
    KBTextExtractionError,
    extract_text_from_markdown_or_text,
    extract_text_from_path,
    extract_text_from_pdf,
    extract_text_from_structured_file,
    normalize_text,
    save_normalized_text_documents,
)
from .policy_enforcer import (
    PolicyConfigError,
    PolicyEnforcer,
    ToolPolicyDeniedError,
)
from .query_allowlist import (
    QueryTemplateNotAllowedError,
    QueryTemplateValidationError,
    execute_query_template,
    load_query_templates_config,
)
from .schema_guard import SchemaGuard, SchemaGuardValidationError
from .tool_call_logging import ToolCallLogger, build_params_hash

__all__ = [
    "PolicyConfigError",
    "PolicyEnforcer",
    "KBSourcesConfigError",
    "KBChunk",
    "KBChunkingConfigError",
    "KBChromaConfigError",
    "KBTextExtractionError",
    "KBSearchTool",
    "QueryTemplateNotAllowedError",
    "QueryTemplateValidationError",
    "SchemaGuard",
    "SchemaGuardValidationError",
    "ToolCallLogger",
    "ToolPolicyDeniedError",
    "ExtractedTextDocument",
    "build_params_hash",
    "build_kb_index",
    "build_kb_index_manifest_row",
    "chunk_extracted_documents",
    "execute_query_template",
    "ensure_kb_collections",
    "extract_text_from_markdown_or_text",
    "extract_text_from_path",
    "extract_text_from_pdf",
    "extract_text_from_structured_file",
    "infer_doc_types_from_chunks",
    "init_kb_chroma_client",
    "load_kb_sources_config",
    "load_kb_chroma_config",
    "load_kb_chunking_config",
    "load_query_templates_config",
    "normalize_text",
    "resolve_kb_sources",
    "save_kb_chunks_jsonl",
    "save_normalized_text_documents",
]

if AlphaLoopResult is not None and alpha_loop is not None and alpha_loop_result_to_dict is not None:
    __all__.extend(["AlphaLoopResult", "alpha_loop", "alpha_loop_result_to_dict"])
