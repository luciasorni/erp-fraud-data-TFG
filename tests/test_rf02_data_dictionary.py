from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.erp_fraud.cli.main import main as cli_main
from src.erp_fraud.storage.data_dictionary import (
    DataDictionaryCompletenessError,
    annotate_dictionary_from_tests,
    build_data_dictionary_draft_from_schema_summary,
    check_dictionary_completeness,
    ensure_min_fields_in_data_dictionary,
    generate_data_dictionary_json_draft,
    load_test_specs_from_catalog,
)


def _base_dictionary() -> dict:
    return {
        "entries": [
            {
                "table": "fraud_1",
                "column": "Belegnummer",
                "type": "VARCHAR",
                "description": "",
                "examples": [],
                "used_in_tests": [],
            },
            {
                "table": "fraud_1",
                "column": "Betrag",
                "type": "DOUBLE",
                "description": "",
                "examples": [],
                "used_in_tests": ["legacy_test"],
            },
        ]
    }


def test_build_data_dictionary_draft_from_schema_summary_creates_entries() -> None:
    schema_summary = {
        "schema_name": "main",
        "table_count": 1,
        "tables": [
            {
                "table_schema": "main",
                "table_name": "fraud_1",
                "columns": [
                    {"name": "Belegnummer", "type": "VARCHAR", "nullable": True, "ordinal_position": 1},
                    {"name": "Betrag", "type": "DOUBLE", "nullable": True, "ordinal_position": 2},
                ],
            }
        ],
    }

    draft = build_data_dictionary_draft_from_schema_summary(
        schema_summary,
        schema_summary_path="schema_summary.json",
        generated_at_utc="2026-02-25T00:00:00+00:00",
    )

    assert draft["entry_format"]["required_fields"] == [
        "table",
        "column",
        "type",
        "description",
        "examples",
        "used_in_tests",
    ]
    assert len(draft["entries"]) == 2
    assert draft["entries"][0]["table"] == "fraud_1"
    assert draft["entries"][0]["column"] == "Belegnummer"


def test_generate_data_dictionary_json_draft_writes_file(tmp_path: Path) -> None:
    schema = {
        "schema_name": "main",
        "table_count": 1,
        "tables": [
            {
                "table_schema": "main",
                "table_name": "t1",
                "columns": [
                    {"name": "c1", "type": "VARCHAR", "nullable": True, "ordinal_position": 1},
                ],
            }
        ],
    }
    schema_path = tmp_path / "schema_summary.json"
    out_path = tmp_path / "data_dictionary.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    generated = generate_data_dictionary_json_draft(schema_path, output_path=out_path)
    loaded = json.loads(generated.read_text(encoding="utf-8"))

    assert generated == out_path
    assert loaded["entries"][0]["table"] == "t1"
    assert loaded["entries"][0]["column"] == "c1"


def test_annotate_dictionary_from_tests_updates_used_in_tests() -> None:
    dictionary = _base_dictionary()
    specs = [
        {
            "id": "T001",
            "data_requirements": {
                "fields": [{"table": "fraud_1", "column": "Belegnummer"}],
            },
        },
        {
            "id": "T002",
            "data_requirements": {
                "table_columns": {"fraud_1": ["Betrag"]},
            },
        },
    ]

    out = annotate_dictionary_from_tests(dictionary, test_specs=specs)
    by_key = {(e["table"], e["column"]): e for e in out["entries"]}
    assert by_key[("fraud_1", "Belegnummer")]["used_in_tests"] == ["T001"]
    assert by_key[("fraud_1", "Betrag")]["used_in_tests"] == ["T002", "legacy_test"]


def test_check_dictionary_completeness_ok_and_error() -> None:
    dictionary = ensure_min_fields_in_data_dictionary(_base_dictionary())
    ok_specs = [
        {
            "id": "T_OK",
            "data_requirements": {"fields": [{"table": "fraud_1", "column": "Belegnummer"}]},
        }
    ]
    summary = check_dictionary_completeness(dictionary, test_specs=ok_specs)
    assert summary["status"] == "OK"
    assert summary["missing_fields_by_test"] == {}

    bad_specs = [
        {
            "id": "T_BAD",
            "data_requirements": {"fields": [{"table": "fraud_1", "column": "NoExiste"}]},
        }
    ]
    with pytest.raises(DataDictionaryCompletenessError, match="T_BAD: fraud_1.NoExiste"):
        check_dictionary_completeness(dictionary, test_specs=bad_specs)


def test_load_test_specs_from_catalog_json(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    (catalog / "a.json").write_text(
        json.dumps({"id": "T001", "data_requirements": {"table_columns": {"fraud_1": ["Belegnummer"]}}}),
        encoding="utf-8",
    )
    specs = load_test_specs_from_catalog(catalog)
    assert len(specs) == 1
    assert specs[0]["id"] == "T001"


def test_cli_validate_dictionary_ok_and_error(tmp_path: Path) -> None:
    dictionary_path = tmp_path / "data_dictionary.json"
    dictionary_path.write_text(json.dumps(_base_dictionary()), encoding="utf-8")

    catalog_ok = tmp_path / "catalog_ok"
    catalog_ok.mkdir(parents=True, exist_ok=True)
    (catalog_ok / "ok.json").write_text(
        json.dumps(
            {
                "id": "T001",
                "data_requirements": {"fields": [{"table": "fraud_1", "column": "Belegnummer"}]},
            }
        ),
        encoding="utf-8",
    )
    rc_ok = cli_main(
        [
            "validate-dictionary",
            "--dictionary",
            str(dictionary_path),
            "--catalog",
            str(catalog_ok),
            "--output-json",
        ]
    )
    assert rc_ok == 0

    catalog_bad = tmp_path / "catalog_bad"
    catalog_bad.mkdir(parents=True, exist_ok=True)
    (catalog_bad / "bad.json").write_text(
        json.dumps(
            {
                "id": "T_BAD",
                "data_requirements": {"fields": [{"table": "fraud_1", "column": "NoExiste"}]},
            }
        ),
        encoding="utf-8",
    )
    rc_bad = cli_main(
        [
            "validate-dictionary",
            "--dictionary",
            str(dictionary_path),
            "--catalog",
            str(catalog_bad),
        ]
    )
    assert rc_bad == 1
