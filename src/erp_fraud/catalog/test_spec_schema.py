"""Esquema base TestSpec para catálogo versionado de tests (RF03-01)."""

from __future__ import annotations

from copy import deepcopy

TEST_SPEC_SCHEMA_VERSION = "1.0.0"

TEST_SPEC_SCHEMA: dict[str, object] = {
    "title": "TestSpec",
    "schema_version": TEST_SPEC_SCHEMA_VERSION,
    "type": "object",
    "required": [
        "id",
        "version",
        "name",
        "fraud_type",
        "red_flag_id",
        "process_step",
        "description",
        "source",
        "expected_output",
        "evidence_columns",
        "data_requirements",
        "logic",
    ],
    "properties": {
        "id": {"type": "string", "pattern": "^TST-[A-Z0-9_-]+$"},
        "version": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"},
        "name": {"type": "string", "minLength": 1},
        "fraud_type": {"type": "string", "minLength": 1},
        "red_flag_id": {"type": "string", "pattern": "^RF-[A-Z0-9-]+$"},
        "process_step": {"type": "string", "minLength": 1},
        "description": {"type": "string", "minLength": 1},
        "source": {
            "type": "object",
            "required": ["catalog", "reference"],
            "properties": {
                "catalog": {"type": "string", "minLength": 1},
                "reference": {"type": "string", "minLength": 1},
                "url": {"type": "string"},
            },
        },
        "data_requirements": {
            "type": "object",
            "required": ["tables"],
            "properties": {
                "tables": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["table", "required_columns"],
                        "properties": {
                            "table": {"type": "string", "minLength": 1},
                            "required_columns": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string", "minLength": 1},
                            },
                            "required_columns_exact": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string", "minLength": 1},
                            },
                        },
                    },
                }
            },
        },
        "expected_output": {
            "type": "object",
            "required": ["primary_entity", "finding_fields"],
            "properties": {
                "primary_entity": {"type": "string", "minLength": 1},
                "finding_fields": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
                "notes": {"type": "string"},
            },
        },
        "evidence_columns": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "logic": {
            "type": "object",
            "required": ["implementation_type"],
            "properties": {
                "implementation_type": {
                    "type": "string",
                    "enum": ["sql", "python"],
                },
                "description": {"type": "string"},
                "sql_ref": {"type": "string"},
                "python_ref": {"type": "string"},
            },
        },
        "enabled": {"type": "boolean"},
        "owner": {"type": "string"},
        "tags": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
    },
    "additionalProperties": False,
}


def get_test_spec_required_fields() -> list[str]:
    """Lista ordenada de campos obligatorios del TestSpec."""
    required = TEST_SPEC_SCHEMA.get("required", [])
    if not isinstance(required, list):
        return []
    return [str(field) for field in required]


def get_test_spec_schema() -> dict[str, object]:
    """Copia defensiva del esquema para uso externo."""
    return deepcopy(TEST_SPEC_SCHEMA)
