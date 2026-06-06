#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"rf11-cross-regression-{stamp}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_rf11_cross_regression",
        description="Ejecuta regresión cruzada P2P vs O2C (RF11-14).",
    )
    parser.add_argument("--run-id", default=None, help="Run ID para evidencia")
    parser.add_argument("--out-dir", default="run_results", help="Directorio base de salida")
    return parser


def _run_check(name: str, command: list[str]) -> dict[str, object]:
    started = time.time()
    proc = subprocess.run(command, capture_output=True, text=True)
    duration_ms = int((time.time() - started) * 1000)
    status = "OK" if proc.returncode == 0 else "ERROR"
    return {
        "name": name,
        "command": command,
        "status": status,
        "returncode": int(proc.returncode),
        "duration_ms": duration_ms,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def main() -> int:
    args = _build_parser().parse_args()
    python_exec = sys.executable or "python3"
    run_id = str(args.run_id).strip() if args.run_id else _default_run_id()
    run_dir = Path(args.out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "rf11_14_cross_regression.json"

    checks = [
        _run_check(
            "p2p_smoke_subset",
            [
                python_exec,
                "-m",
                "pytest",
                "-q",
                "tests/test_rf01_ingest_storage.py",
                "tests/test_rf13_catalog_selection.py",
                "tests/test_rf14_graph_structure.py",
            ],
        ),
        _run_check(
            "o2c_smoke_subset",
            [
                python_exec,
                "-m",
                "pytest",
                "-q",
                "tests/test_rf11_o2c_cli_run.py",
                "tests/test_rf11_o2c_transform.py",
                "tests/test_rf11_o2c_validation.py",
                "tests/test_rf11_o2c_data_dictionary.py",
                "tests/test_rf11_o2c_hypothesis_matrix.py",
                "tests/test_rf11_o2c_taxonomy.py",
                "tests/test_rf11_o2c_catalog_execution.py",
                "tests/test_rf11_o2c_graph_integration.py",
            ],
        ),
    ]

    overall_status = "OK" if all(c["status"] == "OK" for c in checks) else "ERROR"
    payload = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "overall_status": overall_status,
        "checks": checks,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{overall_status} RF11-14 cross regression: {out_path}")
    return 0 if overall_status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
