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

from src.erp_fraud.storage.o2c_hypothesis_matrix import validate_o2c_hypothesis_matrix


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"rf11-o2c-matrix-{stamp}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_rf11_o2c_hypothesis_matrix",
        description="Valida matriz O2C hipótesis->tests->evidencias (RF11-11).",
    )
    parser.add_argument("--run-id", default=None, help="Run ID para evidencia (default: autogenerado)")
    parser.add_argument("--out-dir", default="run_results", help="Directorio base de salida")
    parser.add_argument(
        "--matrix-csv",
        default="docs/o2c/artifacts/rf11_11_o2c_hypothesis_matrix.csv",
        help="Ruta a la matriz CSV O2C",
    )
    parser.add_argument(
        "--canonical-schema-config",
        default="config/canonical_schema_o2c.yaml",
        help="Config schema canónico O2C",
    )
    parser.add_argument(
        "--identity-config",
        default="config/o2c_entity_identity.yaml",
        help="Config de identidad O2C",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    run_id = str(args.run_id).strip() if args.run_id else _default_run_id()
    run_dir = Path(args.out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "rf11_11_o2c_hypothesis_matrix_validation.json"

    payload = validate_o2c_hypothesis_matrix(
        matrix_csv_path=args.matrix_csv,
        canonical_schema_config_path=args.canonical_schema_config,
        identity_config_path=args.identity_config,
    )
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    status = str(payload.get("status", ""))
    print(f"{status} RF11-11 hypothesis matrix: {out_path}")
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
