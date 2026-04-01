"""Dry-run mínimo del flujo AlphaCodium con stubs para CI (AG03-05)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.erp_fraud.agents import PolicyEnforcer, SchemaGuard  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="alphacodium_stub_") as tmp_dir:
        base = Path(tmp_dir)
        tool_log = base / "tool_calls.jsonl"
        schema_path = base / "schema_summary.json"

        schema_payload = {
            "schema_name": "main",
            "table_count": 1,
            "tables": [
                {
                    "table_schema": "main",
                    "table_name": "fraud_1",
                    "columns": [
                        {"name": "Kreditor", "type": "VARCHAR", "nullable": True, "ordinal_position": 1},
                        {"name": "Betrag", "type": "DOUBLE", "nullable": True, "ordinal_position": 2},
                    ],
                }
            ],
        }
        schema_path.write_text(
            json.dumps(schema_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        enforcer = PolicyEnforcer.from_yaml(
            policy_path="config/agent_policies.yaml",
            tools_registry_path="config/tools_registry.yaml",
            tool_call_log_path=tool_log,
        )

        # Simula una llamada permitida.
        enforcer.enforce_and_call(
            agent_id="test_executor",
            node_id="run_tests",
            tool_id="TestCatalog",
            tool_callable=lambda **kwargs: {"status": "OK", "kwargs": kwargs},
            test_id="TST-DUPLICATE-POSTINGS",
        )

        # Simula validación anti-alucinación.
        guard = SchemaGuard.from_paths(
            schema_summary_path=schema_path,
            catalog_path="tests/catalog",
            validate_catalog_schema=True,
        )
        guard.validate_references(
            table_columns=[{"table": "main.fraud_1", "column": "Kreditor"}],
            test_ids=["TST-DUPLICATE-POSTINGS"],
        )

        if not tool_log.exists():
            raise RuntimeError("Dry-run falló: no se generó tool_calls.jsonl")

    print("OK alphacodium dry-run stub")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
