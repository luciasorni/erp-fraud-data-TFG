#!/usr/bin/env python3
"""RF16: explicador de segundo nivel para comparar runs y recomendar acciones de auditoría."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from src.erp_fraud.storage.runs_comparison import (
    compare_runs,
    pick_latest_run_ids_by_process_family,
    write_comparison_outputs,
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RF16 second-level explainer (run comparison + audit recommendations)")
    parser.add_argument("--base-dir", default="run_results", help="Base de runs (default: run_results)")
    parser.add_argument("--run-ids", nargs="*", default=[], help="Run IDs a comparar (1..N)")
    parser.add_argument(
        "--auto-latest-p2p-o2c",
        action="store_true",
        help="Si no pasas run_ids, toma automáticamente el último run p2p y el último o2c",
    )
    parser.add_argument(
        "--analysis-id",
        default="",
        help="ID de análisis RF16 (default: rf16-second-level-<utc>)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_ids = [str(item).strip() for item in args.run_ids if str(item).strip()]
    if not run_ids and args.auto_latest_p2p_o2c:
        run_ids = pick_latest_run_ids_by_process_family(base_dir=args.base_dir)
    if not run_ids:
        raise ValueError("Debes indicar --run-ids o usar --auto-latest-p2p-o2c")

    payload = compare_runs(run_ids=run_ids, base_dir=args.base_dir)

    analysis_id = str(args.analysis_id).strip() or f"rf16-second-level-{_utc_stamp()}"
    out_dir = Path(args.base_dir) / analysis_id
    json_path, md_path = write_comparison_outputs(
        payload=payload,
        output_json_path=out_dir / "rf16_second_level_analysis.json",
        output_md_path=out_dir / "rf16_second_level_analysis.md",
    )

    print(f"RF16 analysis_id: {analysis_id}")
    print(f"RF16 compared runs: {', '.join(run_ids)}")
    print(f"RF16 JSON: {json_path}")
    print(f"RF16 MD: {md_path}")
    print(f"RF16 recommendations: {len(payload.get('recommendations', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
