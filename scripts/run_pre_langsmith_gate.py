"""Release gate previo a RF14b (LangSmith)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


BASE_GATE_COMMANDS: list[list[str]] = [
    ["python3", "scripts/validate_project_schema.py"],
    ["python3", "scripts/validate_required_env.py", "--profile", "pre_langsmith"],
]
PYTEST_GATE_TARGETS: list[str] = [
    "tests/test_rf14_graph_state.py",
    "tests/test_rf14_graph_routing.py",
    "tests/test_rf14_graph_integration.py",
    "tests/test_rf15_validator_and_snapshot.py",
    "tests/test_rf15c_multiagent_integration.py",
    "tests/test_rf15c_scoring_node.py",
    "tests/test_rf18_scoring_end_to_end.py",
    "tests/test_rf13_p2_additional_catalog.py",
    "tests/test_rf13_p2p_hypothesis_matrix.py",
    "tests/test_rf11_o2c_catalog_execution.py",
    "tests/test_rf11_o2c_graph_integration.py",
    "tests/test_rf14b_contracts.py",
    "tests/test_rf14b_env_validation.py",
    "tests/test_rf14b_evaluators.py",
    "tests/test_rf14b_langsmith_dataset.py",
    "tests/test_rf14b_experiments_script.py",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_command(cmd: list[str]) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    ended = datetime.now(timezone.utc)
    return {
        "command": cmd,
        "started_at_utc": started.replace(microsecond=0).isoformat(),
        "ended_at_utc": ended.replace(microsecond=0).isoformat(),
        "duration_ms": int((ended - started).total_seconds() * 1000),
        "returncode": int(proc.returncode),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "status": "OK" if proc.returncode == 0 else "ERROR",
    }


def _resolve_pytest_targets() -> tuple[list[str], list[str]]:
    existing: list[str] = []
    missing: list[str] = []
    for target in PYTEST_GATE_TARGETS:
        if Path(target).exists():
            existing.append(target)
        else:
            missing.append(target)
    return existing, missing


def main() -> int:
    existing_targets, missing_targets = _resolve_pytest_targets()
    if not existing_targets:
        out = Path("run_results/pre_langsmith_gate.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "gate_name": "pre_langsmith",
            "generated_at_utc": _utc_now_iso(),
            "overall_status": "ERROR",
            "checks": [
                {
                    "command": ["python3", "-m", "pytest", "-q"],
                    "status": "ERROR",
                    "returncode": 4,
                    "stdout": "",
                    "stderr": "No pytest targets found for pre-langsmith gate.",
                    "missing_test_targets": PYTEST_GATE_TARGETS,
                }
            ],
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("ERROR: pre-langsmith gate FAILED", file=sys.stderr)
        print(out.as_posix(), file=sys.stderr)
        return 1

    gate_commands = [
        *BASE_GATE_COMMANDS,
        ["python3", "-m", "pytest", "-q", *existing_targets],
    ]

    checks: list[dict[str, Any]] = []
    overall_status = "OK"
    for cmd in gate_commands:
        result = _run_command(cmd)
        if cmd[:3] == ["python3", "-m", "pytest"] and missing_targets:
            result["missing_test_targets"] = missing_targets
        checks.append(result)
        if result["status"] != "OK":
            overall_status = "ERROR"
            break

    payload = {
        "gate_name": "pre_langsmith",
        "generated_at_utc": _utc_now_iso(),
        "overall_status": overall_status,
        "checks": checks,
    }
    out = Path("run_results/pre_langsmith_gate.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if overall_status != "OK":
        print("ERROR: pre-langsmith gate FAILED", file=sys.stderr)
        print(out.as_posix(), file=sys.stderr)
        return 1
    print("OK: pre-langsmith gate PASSED")
    print(out.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
