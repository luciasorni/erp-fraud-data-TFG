"""Dependencias parcheables de nodos (fuente única para tests/runtime)."""

from __future__ import annotations

from ...agents import alpha_loop as _alpha_loop
from ...agents import alpha_loop_result_to_dict as _alpha_loop_result_to_dict
from ...agents.kb_index import build_kb_index as _build_kb_index
from ...agents.kb_search import KBSearchTool as _KBSearchTool
from ...catalog import load_test_specs_from_catalog
from ...catalog.test_runner import TestRunner as _TestRunner

# Expuestas como atributos mutables para compat con monkeypatch en tests.
alpha_loop = _alpha_loop
alpha_loop_result_to_dict = _alpha_loop_result_to_dict
build_kb_index = _build_kb_index
KBSearchTool = _KBSearchTool
TestRunner = _TestRunner


def tool_test_catalog(*, catalog_path: str) -> dict:
    specs = load_test_specs_from_catalog(catalog_path=catalog_path, validate_schema=True)
    tests: list[dict] = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        test_id = str(spec.get("id", "")).strip()
        if not test_id:
            continue
        table_requirements: list[dict] = []
        data_requirements = spec.get("data_requirements", {})
        if isinstance(data_requirements, dict):
            tables = data_requirements.get("tables", [])
            if isinstance(tables, list):
                for table_req in tables:
                    if not isinstance(table_req, dict):
                        continue
                    table_name = str(table_req.get("table", "")).strip()
                    required_columns = table_req.get("required_columns", [])
                    if not isinstance(required_columns, list):
                        required_columns = []
                    cols = [str(col).strip() for col in required_columns if str(col).strip()]
                    if table_name and cols:
                        table_requirements.append(
                            {
                                "table": table_name,
                                "required_columns": cols,
                            }
                        )
        tests.append(
            {
                "id": test_id,
                "fraud_type": str(spec.get("fraud_type", "")).strip(),
                "process_step": str(spec.get("process_step", "")).strip(),
                "name": str(spec.get("name", "")).strip(),
                "table_requirements": table_requirements,
                "tags": [str(tag).strip() for tag in spec.get("tags", []) if str(tag).strip()]
                if isinstance(spec.get("tags"), list)
                else [],
            }
        )
    tests = sorted(tests, key=lambda row: str(row.get("id", "")))
    return {"tests": tests, "count": len(tests)}
