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

from src.erp_fraud.storage.o2c_taxonomy import validate_o2c_taxonomy_alignment


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"rf11-o2c-taxonomy-{stamp}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_rf11_o2c_taxonomy",
        description="Valida alineación de taxonomía O2C con Fraud Tree (RF11-12).",
    )
    parser.add_argument("--run-id", default=None, help="Run ID para evidencia (default: autogenerado)")
    parser.add_argument("--out-dir", default="run_results", help="Directorio base para evidencias")
    parser.add_argument(
        "--matrix-csv",
        default="docs/o2c/artifacts/rf11_11_o2c_hypothesis_matrix.csv",
        help="Matriz O2C hipótesis->tests->evidencias",
    )
    parser.add_argument(
        "--taxonomy-config",
        default="config/fraud_tree_taxonomy.yaml",
        help="Config de taxonomía Fraud Tree",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    run_id = str(args.run_id).strip() if args.run_id else _default_run_id()
    run_dir = Path(args.out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "rf11_12_o2c_taxonomy_validation.json"

    payload = validate_o2c_taxonomy_alignment(
        matrix_csv_path=args.matrix_csv,
        taxonomy_config_path=args.taxonomy_config,
    )
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    status = str(payload.get("status", ""))
    print(f"{status} RF11-12 o2c taxonomy: {out_path}")
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
