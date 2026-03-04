"""Extracción de columnas requeridas desde TestSpec para validación técnica."""

from __future__ import annotations

from typing import Any


def _extract_pairs_from_data_requirements(data_requirements: Any) -> set[tuple[str, str]]:
    """Extrae pares (table, column) desde estructuras flexibles de data_requirements."""
    pairs: set[tuple[str, str]] = set()
    if not isinstance(data_requirements, dict):
        return pairs

    # {"fields": [{"table": "...", "column": "..."}]}
    for key in ("fields", "columns"):
        items = data_requirements.get(key)
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                table = item.get("table") or item.get("table_name")
                column = item.get("column") or item.get("column_name")
                if table and column:
                    pairs.add((str(table), str(column)))

    # {"tables": [{"table": "...", "columns": ["a", "b"]}]}
    tables = data_requirements.get("tables")
    if isinstance(tables, list):
        for item in tables:
            if not isinstance(item, dict):
                continue
            table = item.get("table") or item.get("name") or item.get("table_name")
            columns = item.get("columns") or item.get("required_columns")
            if not table or not isinstance(columns, list):
                continue
            for col in columns:
                if isinstance(col, str):
                    pairs.add((str(table), col))
                elif isinstance(col, dict):
                    column = col.get("column") or col.get("name")
                    if column:
                        pairs.add((str(table), str(column)))

    # {"table_columns": {"fraud_1": ["a", "b"]}}
    for map_key in ("table_columns", "columns_by_table"):
        by_table = data_requirements.get(map_key)
        if isinstance(by_table, dict):
            for table, columns in by_table.items():
                if isinstance(columns, list):
                    for col in columns:
                        if isinstance(col, str):
                            pairs.add((str(table), col))

    # Fallback: {"fraud_1": ["a", "b"]}
    for table, columns in data_requirements.items():
        if table in {"fields", "columns", "tables", "table_columns", "columns_by_table"}:
            continue
        if isinstance(columns, list) and all(isinstance(c, str) for c in columns):
            for col in columns:
                pairs.add((str(table), col))

    return pairs


def extract_required_columns_from_testspecs(test_specs: list[dict]) -> dict[str, list[str]]:
    """Devuelve columnas requeridas por tabla a partir de una lista de TestSpec."""
    required: dict[str, set[str]] = {}
    for spec in test_specs:
        if not isinstance(spec, dict):
            continue
        pairs = _extract_pairs_from_data_requirements(spec.get("data_requirements"))
        for table, column in pairs:
            required.setdefault(table, set()).add(column)

    return {table: sorted(columns) for table, columns in sorted(required.items())}
