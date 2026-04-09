#!/usr/bin/env python3
"""Valida matriz P2P hipótesis->tests->evidencias y guarda evidencia JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.erp_fraud.storage.p2p_hypothesis_matrix import validate_p2p_hypothesis_matrix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RF13 P2P hypothesis matrix validation runner.")
    parser.add_argument("--run-id", required=True, help="Identificador de run para guardar evidencia.")
    parser.add_argument(
        "--matrix-csv",
        default="docs/p2p/artifacts/rf13_p2p_hypothesis_matrix.csv",
        help="Ruta CSV de matriz P2P.",
    )
    parser.add_argument(
        "--catalog-path",
        default="tests/catalog",
        help="Ruta del catálogo de tests P2P.",
    )
    parser.add_argument(
        "--persist-base-dir",
        default="run_results",
        help="Carpeta base de evidencias.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = validate_p2p_hypothesis_matrix(
        matrix_csv_path=args.matrix_csv,
        catalog_path=args.catalog_path,
    )
    run_dir = Path(args.persist_base_dir) / str(args.run_id).strip()
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "rf13_p2p_hypothesis_matrix_validation.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if payload.get("status") != "OK":
        print(f"ERROR RF13 P2P hypothesis matrix: {out}")
        return 1
    print(f"OK RF13 P2P hypothesis matrix: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
