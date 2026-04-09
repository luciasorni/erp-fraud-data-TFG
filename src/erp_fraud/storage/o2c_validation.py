"""Validación técnica de tablas canónicas O2C (RF11-06)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import duckdb


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_yaml(path: str | Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyYAML no disponible") from exc
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe YAML: {p}")
    payload = yaml.safe_load(p.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML inválido (raíz no objeto): {p}")
    return payload


def _q_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _table_exists(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE lower(table_schema) = lower(?) AND lower(table_name) = lower(?)
        LIMIT 1
        """,
        [schema, table],
    ).fetchone()
    return bool(row)


def _available_columns(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE lower(table_schema) = lower(?) AND lower(table_name) = lower(?)
        """,
        [schema, table],
    ).fetchall()
    return {str(r[0]) for r in rows}


def _count_total_rows(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> int:
    row = conn.execute(f'SELECT COUNT(*) FROM {_q_ident(schema)}.{_q_ident(table)}').fetchone()
    return int(row[0] if row else 0)


def _count_null_or_blank(conn: duckdb.DuckDBPyConnection, schema: str, table: str, column: str) -> int:
    query = f"""
      SELECT COUNT(*)
      FROM {_q_ident(schema)}.{_q_ident(table)}
      WHERE {_q_ident(column)} IS NULL
         OR TRIM(CAST({_q_ident(column)} AS VARCHAR)) = ''
    """
    row = conn.execute(query).fetchone()
    return int(row[0] if row else 0)


def _count_unparseable_date(conn: duckdb.DuckDBPyConnection, schema: str, table: str, column: str) -> int:
    query = f"""
      SELECT COUNT(*)
      FROM {_q_ident(schema)}.{_q_ident(table)}
      WHERE {_q_ident(column)} IS NOT NULL
        AND TRIM(CAST({_q_ident(column)} AS VARCHAR)) <> ''
        AND TRY_CAST({_q_ident(column)} AS DATE) IS NULL
        AND TRY_CAST({_q_ident(column)} AS TIMESTAMP) IS NULL
    """
    row = conn.execute(query).fetchone()
    return int(row[0] if row else 0)


def _count_unparseable_amount(conn: duckdb.DuckDBPyConnection, schema: str, table: str, column: str) -> int:
    query = f"""
      SELECT COUNT(*)
      FROM {_q_ident(schema)}.{_q_ident(table)}
      WHERE {_q_ident(column)} IS NOT NULL
        AND TRIM(CAST({_q_ident(column)} AS VARCHAR)) <> ''
        AND TRY_CAST(REPLACE(TRIM(CAST({_q_ident(column)} AS VARCHAR)), ',', '.') AS DOUBLE) IS NULL
    """
    row = conn.execute(query).fetchone()
    return int(row[0] if row else 0)


def build_o2c_validation_report(
    *,
    conn: duckdb.DuckDBPyConnection,
    canonical_schema_config_path: str | Path = "config/canonical_schema_o2c.yaml",
    target_schema: str = "o2c",
) -> dict[str, Any]:
    cfg = _load_yaml(canonical_schema_config_path)
    entities_cfg = cfg.get("entities", {})
    if not isinstance(entities_cfg, dict):
        entities_cfg = {}
    degradation = cfg.get("degradation_policy", {})
    if not isinstance(degradation, dict):
        degradation = {}
    fail_fast = {
        str(x).strip() for x in degradation.get("fail_fast_entities", []) if str(x).strip()
    } if isinstance(degradation.get("fail_fast_entities"), list) else set()
    soft_fail = {
        str(x).strip() for x in degradation.get("soft_fail_entities", []) if str(x).strip()
    } if isinstance(degradation.get("soft_fail_entities"), list) else set()

    checks: list[dict[str, Any]] = []
    critical_errors_count = 0
    warning_findings_count = 0

    entity_table_exists: dict[str, bool] = {}
    for entity, entity_cfg in sorted(entities_cfg.items()):
        exists = _table_exists(conn, target_schema, entity)
        entity_table_exists[entity] = exists
        if not exists:
            if entity in fail_fast:
                critical_errors_count += 1
                checks.append(
                    {
                        "id": f"{entity}.table_exists",
                        "severity": "critical",
                        "status": "ERROR",
                        "message": f"Missing canonical table {target_schema}.{entity}",
                    }
                )
            elif entity in soft_fail:
                warning_findings_count += 1
                checks.append(
                    {
                        "id": f"{entity}.table_exists",
                        "severity": "warning",
                        "status": "SKIPPED",
                        "message": f"Optional canonical table not present: {target_schema}.{entity}",
                    }
                )
            else:
                critical_errors_count += 1
                checks.append(
                    {
                        "id": f"{entity}.table_exists",
                        "severity": "critical",
                        "status": "ERROR",
                        "message": f"Missing canonical table {target_schema}.{entity}",
                    }
                )
            continue

        available = _available_columns(conn, target_schema, entity)
        required_fields = entity_cfg.get("required_fields", []) if isinstance(entity_cfg, dict) else []
        required_names = []
        if isinstance(required_fields, list):
            for field in required_fields:
                if isinstance(field, dict):
                    name = str(field.get("name", "")).strip()
                    if name:
                        required_names.append(name)
        missing_required = [name for name in required_names if name not in available]
        if missing_required:
            critical_errors_count += len(missing_required)
            checks.append(
                {
                    "id": f"{entity}.required_fields",
                    "severity": "critical",
                    "status": "ERROR",
                    "missing_required_fields": sorted(missing_required),
                }
            )
        else:
            checks.append(
                {
                    "id": f"{entity}.required_fields",
                    "severity": "critical",
                    "status": "OK",
                    "required_fields_count": len(required_names),
                }
            )

        total_rows = _count_total_rows(conn, target_schema, entity)
        null_pct_by_field: dict[str, float] = {}
        parse_date_errors: dict[str, int] = {}
        parse_amount_errors: dict[str, int] = {}
        for field in required_fields:
            if not isinstance(field, dict):
                continue
            field_name = str(field.get("name", "")).strip()
            field_type = str(field.get("type", "")).strip().lower()
            if not field_name or field_name not in available:
                continue
            nulls = _count_null_or_blank(conn, target_schema, entity, field_name)
            pct = float((nulls / total_rows) * 100.0) if total_rows > 0 else 0.0
            null_pct_by_field[field_name] = round(pct, 4)
            if pct > 0:
                warning_findings_count += 1

            if "date" in field_type:
                count = _count_unparseable_date(conn, target_schema, entity, field_name)
                if count > 0:
                    parse_date_errors[field_name] = count
                    critical_errors_count += count
            if "decimal" in field_type:
                count = _count_unparseable_amount(conn, target_schema, entity, field_name)
                if count > 0:
                    parse_amount_errors[field_name] = count
                    critical_errors_count += count

        checks.append(
            {
                "id": f"{entity}.null_ratio_required",
                "severity": "warning",
                "status": "OK",
                "row_count": total_rows,
                "null_percentage_by_field": null_pct_by_field,
            }
        )
        checks.append(
            {
                "id": f"{entity}.parse_required",
                "severity": "critical",
                "status": "ERROR" if (parse_date_errors or parse_amount_errors) else "OK",
                "date_parse_errors": parse_date_errors,
                "amount_parse_errors": parse_amount_errors,
            }
        )

    relations = cfg.get("relations", [])
    if not isinstance(relations, list):
        relations = []
    for idx, rel in enumerate(relations, start=1):
        if not isinstance(rel, dict):
            continue
        from_entity = str(rel.get("from_entity", "")).strip()
        to_entity = str(rel.get("to_entity", "")).strip()
        join_keys = rel.get("join_keys", [])
        if not from_entity or not to_entity or not isinstance(join_keys, list):
            continue
        if not entity_table_exists.get(from_entity) or not entity_table_exists.get(to_entity):
            checks.append(
                {
                    "id": f"relation.{idx}",
                    "severity": "warning",
                    "status": "SKIPPED",
                    "message": f"Relation check skipped ({from_entity}->{to_entity}) due to missing table",
                }
            )
            continue
        from_cols = [str(item.get("from", "")).strip() for item in join_keys if isinstance(item, dict)]
        to_cols = [str(item.get("to", "")).strip() for item in join_keys if isinstance(item, dict)]
        if not from_cols or not to_cols or len(from_cols) != len(to_cols):
            continue
        on_clause = " AND ".join(
            [f'f.{_q_ident(fk)} = t.{_q_ident(tk)}' for fk, tk in zip(from_cols, to_cols)]
        )
        from_non_null = " AND ".join([f'f.{_q_ident(fk)} IS NOT NULL' for fk in from_cols]) or "TRUE"
        query = f"""
          SELECT
            COUNT(*) AS total_rows,
            SUM(CASE WHEN t.{_q_ident(to_cols[0])} IS NULL THEN 1 ELSE 0 END) AS unmatched_rows
          FROM {_q_ident(target_schema)}.{_q_ident(from_entity)} f
          LEFT JOIN {_q_ident(target_schema)}.{_q_ident(to_entity)} t
            ON {on_clause}
          WHERE {from_non_null}
        """
        total_rows, unmatched_rows = conn.execute(query).fetchone()
        total_rows = int(total_rows or 0)
        unmatched_rows = int(unmatched_rows or 0)
        unmatched_pct = float((unmatched_rows / total_rows) * 100.0) if total_rows > 0 else 0.0
        if unmatched_rows > 0:
            warning_findings_count += 1
        checks.append(
            {
                "id": f"relation.{idx}",
                "severity": "warning",
                "status": "OK",
                "relation": f"{from_entity}->{to_entity}",
                "total_rows": total_rows,
                "unmatched_rows": unmatched_rows,
                "unmatched_percentage": round(unmatched_pct, 4),
            }
        )

    overall_status = "ERROR" if critical_errors_count > 0 else "OK"
    return {
        "report_version": "1.0.0",
        "generated_at_utc": _utc_now_iso(),
        "process_family": "o2c",
        "target_schema": target_schema,
        "canonical_schema_config_path": str(canonical_schema_config_path),
        "summary": {
            "overall_status": overall_status,
            "critical_errors_count": critical_errors_count,
            "warning_findings_count": warning_findings_count,
            "checks_total": len(checks),
        },
        "checks": checks,
    }


def write_o2c_validation_report_json(
    output_path: str | Path,
    *,
    conn: duckdb.DuckDBPyConnection,
    canonical_schema_config_path: str | Path = "config/canonical_schema_o2c.yaml",
    target_schema: str = "o2c",
) -> Path:
    payload = build_o2c_validation_report(
        conn=conn,
        canonical_schema_config_path=canonical_schema_config_path,
        target_schema=target_schema,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

