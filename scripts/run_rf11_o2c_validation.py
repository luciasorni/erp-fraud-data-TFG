#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.erp_fraud.storage.duckdb_store import get_duckdb_connection
from src.erp_fraud.storage.o2c_validation import write_o2c_validation_report_json


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"rf11-o2c-val-{stamp}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_rf11_o2c_validation",
        description="Ejecuta validación técnica de tablas canónicas O2C (RF11-06).",
    )
    parser.add_argument("--db-path", default="erp.duckdb", help="Ruta DuckDB (default: erp.duckdb)")
    parser.add_argument("--run-id", default=None, help="Run ID para evidencia (default: autogenerado)")
    parser.add_argument("--out-dir", default="run_results", help="Directorio de salida de evidencia")
    parser.add_argument(
        "--canonical-schema-config",
        default="config/canonical_schema_o2c.yaml",
        help="Config de schema canónico O2C",
    )
    parser.add_argument("--target-schema", default="o2c", help="Schema DuckDB canónico")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    run_id = str(args.run_id).strip() if args.run_id else _default_run_id()
    run_dir = Path(args.out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "rf11_06_o2c_validation_report.json"

    conn = get_duckdb_connection(args.db_path)
    try:
        write_o2c_validation_report_json(
            out_path,
            conn=conn,
            canonical_schema_config_path=args.canonical_schema_config,
            target_schema=args.target_schema,
        )
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
        status = str(summary.get("overall_status", ""))
        print(f"{status} RF11-06 validation: {out_path}")
        return 0 if status == "OK" else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
