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
from src.erp_fraud.storage.o2c_transform import O2CTransformError, transform_raw_to_o2c_canonical


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"rf11-o2c-{stamp}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_rf11_o2c_transform",
        description="Ejecuta transformación raw->canónico O2C en DuckDB (RF11-05).",
    )
    parser.add_argument("--db-path", default="erp.duckdb", help="Ruta DuckDB (default: erp.duckdb)")
    parser.add_argument("--run-id", default=None, help="Run ID para evidencia (default: autogenerado)")
    parser.add_argument("--out-dir", default="run_results", help="Directorio de salida de evidencia")
    parser.add_argument(
        "--canonical-schema-config",
        default="config/canonical_schema_o2c.yaml",
        help="Config de schema canónico O2C",
    )
    parser.add_argument(
        "--identity-config",
        default="config/o2c_entity_identity.yaml",
        help="Config de business keys/normalización O2C",
    )
    parser.add_argument(
        "--mapping-config",
        default="config/column_mapping_o2c.yaml",
        help="Config de mapping explícito raw->canónico O2C",
    )
    parser.add_argument("--target-schema", default="o2c", help="Schema DuckDB de salida canónica")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    run_id = str(args.run_id).strip() if args.run_id else _default_run_id()
    run_dir = Path(args.out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / "rf11_05_o2c_transform_evidence.json"

    conn = get_duckdb_connection(args.db_path)
    try:
        payload = transform_raw_to_o2c_canonical(
            conn=conn,
            canonical_schema_config_path=args.canonical_schema_config,
            identity_config_path=args.identity_config,
            mapping_config_path=args.mapping_config,
            target_schema=args.target_schema,
        )
        payload["status"] = "OK"
        payload["generated_at_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        payload["run_id"] = run_id
        payload["db_path"] = str(args.db_path)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"OK RF11-05 transform: {output_path}")
        return 0
    except O2CTransformError as exc:
        payload = {
            "status": "ERROR",
            "error": str(exc),
            "run_id": run_id,
            "db_path": str(args.db_path),
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"ERROR RF11-05 transform: {exc}")
        print(output_path)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
