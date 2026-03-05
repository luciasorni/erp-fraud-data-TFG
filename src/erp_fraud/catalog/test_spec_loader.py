"""Carga y validación de TestSpec desde catálogo (RF03-03)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .test_spec_schema import TEST_SPEC_SCHEMA

SUPPORTED_TESTSPEC_SUFFIXES = {".json", ".yml", ".yaml"}


class TestSpecValidationError(ValueError):
    """Error de validación de esquema en un TestSpec."""


def _load_testspec_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    raw_text = path.read_text(encoding="utf-8")

    if suffix == ".json":
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise TestSpecValidationError(f"{path}: el contenido JSON debe ser un objeto")
        return data

    if suffix in {".yml", ".yaml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"No se puede leer YAML sin PyYAML instalado: {path}") from exc
        data = yaml.safe_load(raw_text)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise TestSpecValidationError(f"{path}: el contenido YAML debe ser un objeto")
        return data

    raise ValueError(f"Formato de TestSpec no soportado: {path}")


def _validate_pattern(value: str, pattern: str, field_name: str, path: Path) -> None:
    if not re.match(pattern, value):
        raise TestSpecValidationError(
            f"{path}: campo '{field_name}' no cumple patrón '{pattern}' (valor='{value}')"
        )


def _validate_required_top_level(spec: dict[str, Any], path: Path) -> None:
    required_fields = TEST_SPEC_SCHEMA.get("required", [])
    if not isinstance(required_fields, list):
        raise RuntimeError("TEST_SPEC_SCHEMA mal formado: 'required' debe ser list")
    missing = [field for field in required_fields if field not in spec]
    if missing:
        raise TestSpecValidationError(f"{path}: faltan campos obligatorios: {', '.join(missing)}")


def _validate_source(source: Any, path: Path) -> None:
    if not isinstance(source, dict):
        raise TestSpecValidationError(f"{path}: 'source' debe ser objeto")
    for field in ("catalog", "reference"):
        value = source.get(field)
        if not isinstance(value, str) or not value.strip():
            raise TestSpecValidationError(f"{path}: 'source.{field}' debe ser string no vacío")
    url = source.get("url")
    if url is not None and not isinstance(url, str):
        raise TestSpecValidationError(f"{path}: 'source.url' debe ser string si se informa")


def _validate_data_requirements(data_requirements: Any, path: Path) -> None:
    if not isinstance(data_requirements, dict):
        raise TestSpecValidationError(f"{path}: 'data_requirements' debe ser objeto")
    tables = data_requirements.get("tables")
    if not isinstance(tables, list) or len(tables) == 0:
        raise TestSpecValidationError(f"{path}: 'data_requirements.tables' debe ser lista no vacía")
    for idx, table_req in enumerate(tables):
        if not isinstance(table_req, dict):
            raise TestSpecValidationError(
                f"{path}: 'data_requirements.tables[{idx}]' debe ser objeto"
            )
        table_name = table_req.get("table")
        if not isinstance(table_name, str) or not table_name.strip():
            raise TestSpecValidationError(
                f"{path}: 'data_requirements.tables[{idx}].table' debe ser string no vacío"
            )
        required_columns = table_req.get("required_columns")
        if not isinstance(required_columns, list) or len(required_columns) == 0:
            raise TestSpecValidationError(
                f"{path}: 'data_requirements.tables[{idx}].required_columns' debe ser lista no vacía"
            )
        for col_idx, column in enumerate(required_columns):
            if not isinstance(column, str) or not column.strip():
                raise TestSpecValidationError(
                    f"{path}: columna inválida en "
                    f"'data_requirements.tables[{idx}].required_columns[{col_idx}]'"
                )

        required_columns_exact = table_req.get("required_columns_exact")
        if required_columns_exact is not None:
            if not isinstance(required_columns_exact, list) or len(required_columns_exact) == 0:
                raise TestSpecValidationError(
                    f"{path}: 'data_requirements.tables[{idx}].required_columns_exact' "
                    "debe ser lista no vacía"
                )
            for col_idx, column in enumerate(required_columns_exact):
                if not isinstance(column, str) or not column.strip():
                    raise TestSpecValidationError(
                        f"{path}: columna inválida en "
                        f"'data_requirements.tables[{idx}].required_columns_exact[{col_idx}]'"
                    )
            if set(required_columns_exact) != set(required_columns):
                raise TestSpecValidationError(
                    f"{path}: 'required_columns_exact' debe contener exactamente los mismos "
                    f"campos que 'required_columns' en tables[{idx}]"
                )


def _validate_logic(logic: Any, path: Path) -> None:
    if not isinstance(logic, dict):
        raise TestSpecValidationError(f"{path}: 'logic' debe ser objeto")
    implementation_type = logic.get("implementation_type")
    if implementation_type not in {"sql", "python"}:
        raise TestSpecValidationError(
            f"{path}: 'logic.implementation_type' debe ser 'sql' o 'python'"
        )
    for optional_key in ("description", "sql_ref", "python_ref"):
        value = logic.get(optional_key)
        if value is not None and not isinstance(value, str):
            raise TestSpecValidationError(f"{path}: 'logic.{optional_key}' debe ser string si se informa")


def validate_test_spec(spec: dict[str, Any], *, source_path: str | Path = "<memory>") -> dict[str, Any]:
    """Valida un TestSpec y devuelve el mismo objeto si es válido."""
    path = Path(source_path)
    if not isinstance(spec, dict):
        raise TestSpecValidationError(f"{path}: TestSpec debe ser objeto")

    _validate_required_top_level(spec, path)

    test_id = spec.get("id")
    if not isinstance(test_id, str) or not test_id.strip():
        raise TestSpecValidationError(f"{path}: 'id' debe ser string no vacío")
    _validate_pattern(test_id, r"^TST-[A-Z0-9_-]+$", "id", path)

    version = spec.get("version")
    if not isinstance(version, str) or not version.strip():
        raise TestSpecValidationError(f"{path}: 'version' debe ser string no vacío")
    _validate_pattern(version, r"^[0-9]+\.[0-9]+\.[0-9]+$", "version", path)

    for field in ("name", "fraud_type", "description"):
        value = spec.get(field)
        if not isinstance(value, str) or not value.strip():
            raise TestSpecValidationError(f"{path}: '{field}' debe ser string no vacío")

    _validate_source(spec.get("source"), path)
    _validate_data_requirements(spec.get("data_requirements"), path)
    _validate_logic(spec.get("logic"), path)

    enabled = spec.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        raise TestSpecValidationError(f"{path}: 'enabled' debe ser boolean si se informa")

    owner = spec.get("owner")
    if owner is not None and not isinstance(owner, str):
        raise TestSpecValidationError(f"{path}: 'owner' debe ser string si se informa")

    tags = spec.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            raise TestSpecValidationError(f"{path}: 'tags' debe ser lista de strings")
        for idx, tag in enumerate(tags):
            if not isinstance(tag, str) or not tag.strip():
                raise TestSpecValidationError(f"{path}: 'tags[{idx}]' debe ser string no vacío")

    return spec


def load_test_specs_from_catalog(
    catalog_path: str | Path = "tests/catalog",
    *,
    validate_schema: bool = True,
) -> list[dict[str, Any]]:
    """Carga TestSpecs del catálogo y opcionalmente valida el esquema."""
    path = Path(catalog_path)
    if not path.exists():
        return []

    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_TESTSPEC_SUFFIXES:
            raise ValueError(f"Formato de TestSpec no soportado: {path}")
        spec = _load_testspec_file(path)
        if validate_schema:
            validate_test_spec(spec, source_path=path)
        return [spec]

    specs: list[dict[str, Any]] = []
    for file_path in sorted(path.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in SUPPORTED_TESTSPEC_SUFFIXES:
            continue
        spec = _load_testspec_file(file_path)
        if validate_schema:
            validate_test_spec(spec, source_path=file_path)
        specs.append(spec)
    return specs
