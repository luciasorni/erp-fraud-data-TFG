from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURES_DIR = Path("tests/fixtures/prompts")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path}: expected JSON object"
    return payload


def _validate_common_output_shape(payload: dict[str, Any], *, fixture_name: str) -> None:
    required = {"status", "summary", "decisions", "evidence", "next_actions", "errors"}
    missing = sorted(required.difference(payload.keys()))
    assert not missing, f"{fixture_name}: missing required fields {missing}"

    assert payload["status"] in {"OK", "NEEDS_DATA", "ERROR"}, f"{fixture_name}: invalid status"
    assert isinstance(payload["summary"], str)
    assert isinstance(payload["decisions"], list)
    assert isinstance(payload["evidence"], list)
    assert isinstance(payload["next_actions"], list)
    assert isinstance(payload["errors"], list)

    for idx, row in enumerate(payload["decisions"]):
        assert isinstance(row, dict), f"{fixture_name}: decisions[{idx}] must be object"
        assert isinstance(row.get("id"), str) and row.get("id", "").strip()
        assert isinstance(row.get("reason"), str)
        confidence = row.get("confidence")
        assert isinstance(confidence, (int, float)), f"{fixture_name}: decisions[{idx}].confidence invalid"
        assert 0.0 <= float(confidence) <= 1.0, f"{fixture_name}: decisions[{idx}].confidence out of range"


def _validate_no_inventions(
    payload: dict[str, Any],
    *,
    fixture_name: str,
    allowed_test_ids: set[str],
    allowed_tables: dict[str, set[str]],
) -> None:
    for idx, row in enumerate(payload.get("evidence", [])):
        assert isinstance(row, dict), f"{fixture_name}: evidence[{idx}] must be object"
        test_id = str(row.get("test_id", "")).strip()
        table = str(row.get("table", "")).strip()
        columns = row.get("columns", [])
        assert test_id in allowed_test_ids, f"{fixture_name}: invented test_id {test_id}"
        assert table in allowed_tables, f"{fixture_name}: invented table {table}"
        assert isinstance(columns, list), f"{fixture_name}: evidence[{idx}].columns must be list"
        unknown_columns = sorted({str(col) for col in columns if str(col) not in allowed_tables[table]})
        assert not unknown_columns, f"{fixture_name}: invented columns {unknown_columns}"


def _validate_kb_citations(payload: dict[str, Any], *, fixture_name: str, allowed_sources: set[str]) -> None:
    citations = payload.get("kb_citations", [])
    assert isinstance(citations, list), f"{fixture_name}: kb_citations must be list"
    assert citations, f"{fixture_name}: kb_citations required for this fixture"
    for idx, row in enumerate(citations):
        assert isinstance(row, dict), f"{fixture_name}: kb_citations[{idx}] must be object"
        source_id = str(row.get("source_id", "")).strip()
        chunk_id = str(row.get("chunk_id", "")).strip()
        assert source_id in allowed_sources, f"{fixture_name}: unknown kb source_id {source_id}"
        assert chunk_id, f"{fixture_name}: empty chunk_id in citation {idx}"


def test_ag03_11_prompt_snapshots_validate_schema_and_references() -> None:
    context = _load_json(FIXTURES_DIR / "context.json")
    allowed_test_ids = {str(item).strip() for item in context["allowed_test_ids"]}
    allowed_tables = {
        str(table).strip(): {str(col).strip() for col in columns}
        for table, columns in context["allowed_tables"].items()
    }
    allowed_sources = {str(item).strip() for item in context["allowed_kb_source_ids"]}

    fixtures = [
        ("hypothesis_planner__v001.output.json", True),
        ("test_planner__v001.output.json", False),
        ("expert_explainer__v001.output.json", True),
        ("scoring__v001.output.json", False),
    ]
    for file_name, require_citations in fixtures:
        payload = _load_json(FIXTURES_DIR / file_name)
        _validate_common_output_shape(payload, fixture_name=file_name)
        _validate_no_inventions(
            payload,
            fixture_name=file_name,
            allowed_test_ids=allowed_test_ids,
            allowed_tables=allowed_tables,
        )
        if require_citations:
            _validate_kb_citations(payload, fixture_name=file_name, allowed_sources=allowed_sources)

    test_planner = _load_json(FIXTURES_DIR / "test_planner__v001.output.json")
    for idx, row in enumerate(test_planner["decisions"]):
        test_id = str(row.get("id", "")).strip()
        assert test_id in allowed_test_ids, f"test_planner decision[{idx}] invents test_id {test_id}"

