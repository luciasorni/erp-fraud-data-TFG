"""SchemaGuard para validar referencias de tablas/columnas/tests (RF15b-04)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..catalog import load_test_specs_from_catalog


class SchemaGuardValidationError(ValueError):
    """Error de validación de referencias contra esquema/catálogo."""


class SchemaGuard:
    """Validador de referencias para bloquear alucinaciones de schema/test_id."""

    def __init__(
        self,
        *,
        schema_summary: dict[str, Any],
        catalog_specs: list[dict[str, Any]],
    ) -> None:
        self.schema_summary = dict(schema_summary)
        self.catalog_specs = list(catalog_specs)
        self._tables, self._columns_by_table = self._index_schema_summary(self.schema_summary)
        self._test_ids = {
            str(spec.get("id")).strip().lower()
            for spec in self.catalog_specs
            if str(spec.get("id", "")).strip()
        }

    @classmethod
    def from_paths(
        cls,
        *,
        schema_summary_path: str | Path,
        catalog_path: str | Path = "tests/catalog",
        validate_catalog_schema: bool = True,
    ) -> "SchemaGuard":
        summary_path = Path(schema_summary_path)
        if not summary_path.exists():
            raise FileNotFoundError(f"No existe schema_summary: {summary_path}")
        raw = summary_path.read_text(encoding="utf-8").strip()
        if not raw:
            raise SchemaGuardValidationError(f"schema_summary vacío: {summary_path}")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise SchemaGuardValidationError("schema_summary debe ser un objeto JSON")

        specs = load_test_specs_from_catalog(
            catalog_path,
            validate_schema=validate_catalog_schema,
        )
        return cls(schema_summary=payload, catalog_specs=specs)

    @staticmethod
    def _index_schema_summary(summary: dict[str, Any]) -> tuple[set[str], dict[str, set[str]]]:
        tables = summary.get("tables")
        if not isinstance(tables, list):
            raise SchemaGuardValidationError("schema_summary inválido: falta lista 'tables'")

        table_names: set[str] = set()
        columns_by_table: dict[str, set[str]] = {}

        for idx, table in enumerate(tables):
            if not isinstance(table, dict):
                raise SchemaGuardValidationError(f"schema_summary inválido: tables[{idx}] no es objeto")
            table_name = str(table.get("table_name", "")).strip()
            table_schema = str(table.get("table_schema", "")).strip()
            if not table_name:
                raise SchemaGuardValidationError(f"schema_summary inválido: tables[{idx}].table_name vacío")
            full_name = f"{table_schema}.{table_name}" if table_schema else table_name

            aliases = {table_name.lower(), full_name.lower()}
            table_names.update(aliases)

            columns = table.get("columns")
            if not isinstance(columns, list):
                raise SchemaGuardValidationError(
                    f"schema_summary inválido: tables[{idx}].columns debe ser lista"
                )
            colset = {
                str(col.get("name", "")).strip().lower()
                for col in columns
                if isinstance(col, dict) and str(col.get("name", "")).strip()
            }
            for alias in aliases:
                columns_by_table[alias] = set(colset)

        return table_names, columns_by_table

    def validate_test_id(self, test_id: str) -> None:
        if not isinstance(test_id, str) or not test_id.strip():
            raise SchemaGuardValidationError("test_id debe ser string no vacío")
        normalized = test_id.strip().lower()
        if normalized not in self._test_ids:
            raise SchemaGuardValidationError(f"test_id no existe en catálogo: {test_id}")

    def validate_table(self, table: str) -> None:
        if not isinstance(table, str) or not table.strip():
            raise SchemaGuardValidationError("table debe ser string no vacío")
        normalized = table.strip().lower()
        if normalized not in self._tables:
            raise SchemaGuardValidationError(f"tabla no existe en schema_summary: {table}")

    def validate_column(self, *, table: str, column: str) -> None:
        self.validate_table(table)
        if not isinstance(column, str) or not column.strip():
            raise SchemaGuardValidationError("column debe ser string no vacío")
        normalized_table = table.strip().lower()
        normalized_col = column.strip().lower()
        known = self._columns_by_table.get(normalized_table, set())
        if normalized_col not in known:
            raise SchemaGuardValidationError(
                f"columna no existe en schema_summary: {table}.{column}"
            )

    def validate_references(
        self,
        *,
        table_columns: list[dict[str, str]] | None = None,
        test_ids: list[str] | None = None,
    ) -> None:
        for ref in table_columns or []:
            if not isinstance(ref, dict):
                raise SchemaGuardValidationError("Cada referencia table_columns debe ser objeto")
            table = str(ref.get("table", "")).strip()
            column = str(ref.get("column", "")).strip()
            if not table or not column:
                raise SchemaGuardValidationError(
                    "Cada referencia table_columns requiere 'table' y 'column'"
                )
            self.validate_column(table=table, column=column)

        for test_id in test_ids or []:
            self.validate_test_id(test_id)
