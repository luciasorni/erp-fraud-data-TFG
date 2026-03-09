from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.erp_fraud.catalog import (
    build_entity_key,
    parse_entity_key,
    sort_result_rows_stable,
    validate_result_schema,
    write_test_results_by_test_id,
)


def test_validate_result_schema_ok() -> None:
    df = pd.DataFrame(
        [
            {
                "entity_key": "belegnummer=49000123|kreditor=100045",
                "keys": {"belegnummer": "49000123", "kreditor": "100045"},
                "evidence_columns": ["Belegnummer", "Kreditor"],
                "metrics": {"duplicate_count": 2},
            }
        ]
    )
    validate_result_schema(df)


def test_validate_result_schema_missing_columns_error() -> None:
    df = pd.DataFrame([{"entity_key": "x"}])
    with pytest.raises(ValueError, match="faltan columnas obligatorias"):
        validate_result_schema(df)


def test_entity_key_build_and_parse_roundtrip() -> None:
    keys = {"kreditor": "100045", "belegnummer": "49000123", "position": "10"}
    entity_key = build_entity_key(keys)
    assert entity_key == "belegnummer=49000123|kreditor=100045|position=10"
    parsed = parse_entity_key(entity_key)
    assert parsed == {
        "belegnummer": "49000123",
        "kreditor": "100045",
        "position": "10",
    }


def test_entity_key_rejects_reserved_chars() -> None:
    with pytest.raises(ValueError, match="separadores reservados"):
        build_entity_key({"kreditor": "100|045"})


def test_sort_result_rows_stable_is_deterministic() -> None:
    rows = [
        {"entity_key": "kreditor=200|belegnummer=2", "keys": {"kreditor": "200", "belegnummer": "2"}, "x": 2},
        {"entity_key": "kreditor=100|belegnummer=1", "keys": {"kreditor": "100", "belegnummer": "1"}, "x": 1},
        {"entity_key": "kreditor=100|belegnummer=1", "keys": {"kreditor": "100", "belegnummer": "1"}, "x": 0},
    ]
    sorted_rows = sort_result_rows_stable(rows)
    assert [r["x"] for r in sorted_rows] == [0, 1, 2]


def test_write_test_results_by_test_id_writes_jsonl_and_sample(tmp_path: Path) -> None:
    test_results = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "rows": [
                {"entity_key": "belegnummer=2|kreditor=200", "keys": {"belegnummer": "2", "kreditor": "200"}},
                {"entity_key": "belegnummer=1|kreditor=100", "keys": {"belegnummer": "1", "kreditor": "100"}},
            ],
        }
    ]

    written = write_test_results_by_test_id(
        run_dir=tmp_path,
        test_results=test_results,
        formats=("jsonl",),
        sample_top_n=1,
    )

    paths = written["TST-DUPLICATE-POSTINGS"]
    jsonl_path = Path(paths["jsonl"])
    sample_path = Path(paths["sample_json"])

    assert jsonl_path.exists()
    assert sample_path.exists()

    lines = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [row["entity_key"] for row in lines] == [
        "belegnummer=1|kreditor=100",
        "belegnummer=2|kreditor=200",
    ]

    sample_payload = json.loads(sample_path.read_text(encoding="utf-8"))
    assert sample_payload["sample_limit"] == 1
    assert sample_payload["sample_size"] == 1
    assert len(sample_payload["rows"]) == 1

