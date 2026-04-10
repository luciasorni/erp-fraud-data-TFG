#!/usr/bin/env python3
# ruff: noqa: E402
"""RF15c-14: ejecución manual E2E + evidencia de trazas (LangSmith opcional)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.erp_fraud.graph import run_graph_full


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class LangSmithConfigSnapshot:
    tracing_enabled: bool
    api_key_present: bool
    project: str
    endpoint: str
    trace_link: str


def resolve_langsmith_snapshot(*, explicit_trace_link: str = "") -> LangSmithConfigSnapshot:
    tracing_raw = str(os.getenv("LANGSMITH_TRACING", "")).strip().lower()
    tracing_v2_raw = str(os.getenv("LANGCHAIN_TRACING_V2", "")).strip().lower()
    tracing_enabled = tracing_raw in {"1", "true", "yes", "on"} or tracing_v2_raw in {
        "1",
        "true",
        "yes",
        "on",
    }
    api_key_present = bool(str(os.getenv("LANGSMITH_API_KEY", "")).strip())
    project = str(os.getenv("LANGSMITH_PROJECT", "")).strip()
    endpoint = str(os.getenv("LANGSMITH_ENDPOINT", "")).strip()
    trace_link = explicit_trace_link.strip() or str(os.getenv("LANGSMITH_TRACE_LINK", "")).strip()
    return LangSmithConfigSnapshot(
        tracing_enabled=tracing_enabled,
        api_key_present=api_key_present,
        project=project,
        endpoint=endpoint,
        trace_link=trace_link,
    )


def build_rf15c_14_evidence_payload(
    *,
    run_id: str,
    run_metadata: dict[str, Any],
    langsmith: LangSmithConfigSnapshot,
    llm_mode: str,
    notes: str,
) -> dict[str, Any]:
    artifacts = run_metadata.get("persist_artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    return {
        "rf_task": "RF15c-14",
        "generated_at_utc": _utc_now_iso(),
        "run_id": run_id,
        "graph_status": str(run_metadata.get("graph_status", "")).strip(),
        "node_status": run_metadata.get("node_status", {}),
        "persist_manifest_path": str(run_metadata.get("persist_manifest_path", "")).strip(),
        "persist_artifacts": artifacts,
        "langsmith": asdict(langsmith),
        "llm_mode": llm_mode,
        "notes": notes.strip(),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RF15c-14 manual E2E runner + evidence writer.")
    parser.add_argument("--run-id", required=True, help="Run ID manual para evidencia de tutor.")
    parser.add_argument(
        "--schema-summary-path",
        required=True,
        help="Ruta a schema_summary.json para ejecutar el grafo sin ingest desde zip.",
    )
    parser.add_argument("--dataset-hash", default="manual-rf15c14", help="Dataset hash lógico para metadata.")
    parser.add_argument("--input-zip", default="manual-input", help="Etiqueta de input para metadata.")
    parser.add_argument("--catalog-path", default="tests/catalog", help="Ruta de catálogo de tests.")
    parser.add_argument("--persist-base-dir", default="run_results", help="Directorio base de outputs.")
    parser.add_argument("--weights-config", default="config/weights.yaml", help="Ruta weights para scoring.")
    parser.add_argument("--kb-index-enabled", action="store_true", help="Activa kb_index en este run manual.")
    parser.add_argument("--kb-search-enabled", action="store_true", help="Activa KBSearch en planner/explainer.")
    parser.add_argument("--langsmith-trace-link", default="", help="URL de traza manual capturada en LangSmith.")
    parser.add_argument(
        "--llm-mode",
        default="stub",
        choices=["stub", "real"],
        help="Modo de ejecución LLM para nodos habilitados.",
    )
    parser.add_argument(
        "--process-family",
        default="p2p",
        choices=["p2p", "o2c"],
        help="Familia de proceso para metadata/ruteo de catálogo.",
    )
    parser.add_argument("--db-path", default="erp.duckdb", help="Ruta DuckDB a usar por executor.")
    parser.add_argument("--schema-name", default="main", help="Schema DuckDB a usar por executor.")
    parser.add_argument("--table-name", default="fraud_1", help="Tabla por defecto de executor.")
    parser.add_argument(
        "--hypothesis-max-items",
        type=int,
        default=3,
        help="Máximo de hipótesis a generar en hypothesis_planner.",
    )
    parser.add_argument(
        "--test-planner-top-n",
        type=int,
        default=3,
        help="Máximo de tests por hipótesis en test_planner.",
    )
    parser.add_argument(
        "--test-planner-min-per-hypothesis-real",
        type=int,
        default=1,
        help="Mínimo de tests por hipótesis cuando llm_mode=real (cobertura anti-concentración).",
    )
    parser.add_argument("--notes", default="", help="Notas libres para contexto del tutor.")
    parser.add_argument(
        "--rf16-auto-latest-p2p-o2c",
        action="store_true",
        help="RF16: compara automáticamente último run P2P+O2C además del run actual.",
    )
    parser.add_argument(
        "--rf16-compare-run-ids",
        default="",
        help="RF16: run_ids explícitos a comparar (coma separada).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = str(args.run_id).strip()
    schema_summary_path = Path(str(args.schema_summary_path).strip())
    if not schema_summary_path.exists():
        raise FileNotFoundError(f"No existe schema_summary_path: {schema_summary_path}")
    try:
        schema_payload = json.loads(schema_summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(
            f"schema_summary_path inválido (debe ser JSON no vacío): {schema_summary_path}"
        ) from exc
    if not isinstance(schema_payload, dict):
        raise ValueError(
            f"schema_summary_path inválido (raíz JSON debe ser objeto): {schema_summary_path}"
        )

    out = run_graph_full(
        run_id=run_id,
        dataset_hash=str(args.dataset_hash).strip(),
        input_zip=str(args.input_zip).strip(),
        run_metadata_overrides={
            "schema_summary_path": str(schema_summary_path),
            "catalog_path": str(args.catalog_path).strip(),
            "persist_base_dir": str(args.persist_base_dir).strip(),
            "weights_config": str(args.weights_config).strip(),
            "llm_mode": str(args.llm_mode).strip(),
            "process_family": str(args.process_family).strip(),
            "db_path": str(args.db_path).strip(),
            "schema_name": str(args.schema_name).strip(),
            "table_name": str(args.table_name).strip(),
            "kb_index_enabled": bool(args.kb_index_enabled),
            "kb_search_enabled": bool(args.kb_search_enabled),
            "scoring_top_k": 20,
            "hypothesis_max_items": int(args.hypothesis_max_items),
            "test_planner_top_n": int(args.test_planner_top_n),
            "test_planner_min_per_hypothesis_real": int(args.test_planner_min_per_hypothesis_real),
            "executor_timeout_ms": 3000,
            "rf16_include_current_run": True,
            "rf16_auto_latest_p2p_o2c": bool(args.rf16_auto_latest_p2p_o2c),
            "rf16_compare_run_ids": [
                item.strip()
                for item in str(args.rf16_compare_run_ids).split(",")
                if item.strip()
            ],
            "rf16_base_dir": str(args.persist_base_dir).strip(),
        },
    )

    metadata = out.run_metadata if isinstance(out.run_metadata, dict) else {}
    langsmith = resolve_langsmith_snapshot(explicit_trace_link=str(args.langsmith_trace_link))
    evidence = build_rf15c_14_evidence_payload(
        run_id=run_id,
        run_metadata=metadata,
        langsmith=langsmith,
        llm_mode=str(args.llm_mode).strip(),
        notes=str(args.notes),
    )

    run_dir = Path(str(args.persist_base_dir).strip()) / run_id
    evidence_path = run_dir / "rf15c_14_manual_evidence.json"
    _write_json(evidence_path, evidence)
    print(f"RF15c-14 evidence: {evidence_path}")
    trace_link = (
        str(metadata.get("langsmith_trace_link", "")).strip()
        or str(metadata.get("langsmith_runs", {}).get("trace_link", "")).strip()
        or str(langsmith.trace_link).strip()
    )
    if trace_link:
        print(f"LangSmith trace link: {trace_link}")
    else:
        print("LangSmith trace link: N/A")
        ls_runs = metadata.get("langsmith_runs", {})
        if isinstance(ls_runs, dict):
            status = str(ls_runs.get("status", "")).strip() or "UNKNOWN"
            reason = str(ls_runs.get("reason", "")).strip() or "n/a"
            print(f"LangSmith publish status: {status} ({reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
