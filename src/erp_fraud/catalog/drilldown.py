"""Drilldown seguro por test_id + keys (RF06-03)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..storage.duckdb_store import DEFAULT_DUCKDB_PATH, get_duckdb_connection
from .drilldown_keys import normalize_drilldown_keys, validate_minimum_keys_for_test_id
from .drilldown_templates import get_drilldown_query_id_for_test_id

DEFAULT_DRILLDOWN_LIMIT = 200
MAX_DRILLDOWN_LIMIT = 200


def _eq_normalized_sql(column_expr: str) -> str:
    return (
        f"REGEXP_REPLACE(TRIM(CAST({column_expr} AS VARCHAR)), '\\.0+$', '') = "
        f"REGEXP_REPLACE(TRIM(CAST(? AS VARCHAR)), '\\.0+$', '')"
    )


def _normalize_limit(limit_rows: int) -> int:
    if not isinstance(limit_rows, int):
        raise TypeError("limit_rows debe ser int")
    if limit_rows <= 0:
        raise ValueError("limit_rows debe ser > 0")
    return min(limit_rows, MAX_DRILLDOWN_LIMIT)


def _normalize_order_direction(order_direction: str) -> str:
    value = str(order_direction or "").strip().upper()
    if value not in {"ASC", "DESC"}:
        raise ValueError("order_direction debe ser 'ASC' o 'DESC'")
    return value


def _build_drilldown_query_and_params(
    *,
    test_id: str,
    keys: dict[str, str],
    query_id: str | None = None,
    schema_name: str = "main",
    table_name: str = "fraud_1",
    limit_rows: int = DEFAULT_DRILLDOWN_LIMIT,
    order_direction: str = "ASC",
    extra_filters: dict[str, str] | None = None,
) -> tuple[str, list[object]]:
    resolved_query_id = str(query_id or "").strip() or get_drilldown_query_id_for_test_id(test_id)
    normalized_keys = normalize_drilldown_keys(keys)
    validation_keys = dict(normalized_keys)
    if resolved_query_id == "drilldown_duplicate_material_items_v1" and "kreditor" not in validation_keys:
        validation_keys["kreditor"] = "__optional__"
    validate_minimum_keys_for_test_id(test_id, validation_keys)
    resolved_limit = _normalize_limit(limit_rows)
    resolved_order_direction = _normalize_order_direction(order_direction)
    filters = dict(extra_filters or {})

    table_ref = f'"{schema_name}"."{table_name}"'

    if resolved_query_id == "drilldown_duplicate_postings_v1":
        if any(key not in {"Transaktionsart"} for key in filters.keys()):
            raise ValueError("extra_filters no permitidos para duplicate_postings; permitido: Transaktionsart")
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE REGEXP_REPLACE(CAST("Kreditor" AS VARCHAR), '\\.0+$', '') =
                  REGEXP_REPLACE(CAST(? AS VARCHAR), '\\.0+$', '')
              AND REGEXP_REPLACE(CAST("Belegnummer" AS VARCHAR), '\\.0+$', '') =
                  REGEXP_REPLACE(CAST(? AS VARCHAR), '\\.0+$', '')
              AND REGEXP_REPLACE(CAST("Position" AS VARCHAR), '\\.0+$', '') =
                  REGEXP_REPLACE(CAST(? AS VARCHAR), '\\.0+$', '')
              AND (
                    (TRY_CAST("Betrag" AS DOUBLE) IS NULL AND TRY_CAST(? AS DOUBLE) IS NULL)
                    OR ABS(TRY_CAST("Betrag" AS DOUBLE) - TRY_CAST(? AS DOUBLE)) < 1e-9
                  )
              AND (? IS NULL OR "Transaktionsart" = ?)
            ORDER BY "Belegnummer" {resolved_order_direction}, "Position" {resolved_order_direction}
            LIMIT ?
        """
        params: list[object] = [
            normalized_keys["kreditor"],
            normalized_keys["belegnummer"],
            normalized_keys["position"],
            normalized_keys["betrag"],
            normalized_keys["betrag"],
            filters.get("Transaktionsart"),
            filters.get("Transaktionsart"),
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_unusual_amount_by_vendor_v1":
        if any(key not in {"Transaktionsart"} for key in filters.keys()):
            raise ValueError(
                "extra_filters no permitidos para unusual_amount_by_vendor; permitido: Transaktionsart"
            )
        transaction_type_filter = filters.get("Transaktionsart") or normalized_keys.get("transaktionsart")
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE {_eq_normalized_sql('"Kreditor"')}
              AND TRY_CAST("Betrag" AS DOUBLE) = TRY_CAST(? AS DOUBLE)
              AND (? IS NULL OR "Transaktionsart" = ?)
            ORDER BY "Kreditor" {resolved_order_direction}
            LIMIT ?
        """
        params = [
            normalized_keys["kreditor"],
            normalized_keys["betrag"],
            transaction_type_filter,
            transaction_type_filter,
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_round_dollar_payments_v1":
        if any(key not in {"Transaktionsart"} for key in filters.keys()):
            raise ValueError(
                "extra_filters no permitidos para round_dollar_payments; permitido: Transaktionsart"
            )
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE {_eq_normalized_sql('"Kreditor"')}
              AND {_eq_normalized_sql('"Belegnummer"')}
              AND ABS(TRY_CAST("Betrag" AS DOUBLE) - TRY_CAST(? AS DOUBLE)) < 1e-9
              AND (? IS NULL OR "Transaktionsart" = ?)
            ORDER BY "Belegnummer" {resolved_order_direction}
            LIMIT ?
        """
        params = [
            normalized_keys["kreditor"],
            normalized_keys["belegnummer"],
            normalized_keys["betrag"],
            filters.get("Transaktionsart"),
            filters.get("Transaktionsart"),
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_just_below_auth_threshold_v1":
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE {_eq_normalized_sql('"Kreditor"')}
              AND {_eq_normalized_sql('"Belegnummer"')}
              AND ABS(TRY_CAST("Betrag" AS DOUBLE) - TRY_CAST(? AS DOUBLE)) < 1e-9
            ORDER BY "Belegnummer" {resolved_order_direction}
            LIMIT ?
        """
        params = [
            normalized_keys["kreditor"],
            normalized_keys["belegnummer"],
            normalized_keys["betrag"],
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_split_payments_near_limit_v1":
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE {_eq_normalized_sql('"Kreditor"')}
              AND {_eq_normalized_sql('"Belegnummer"')}
            ORDER BY "Position" {resolved_order_direction}
            LIMIT ?
        """
        params = [
            normalized_keys["kreditor"],
            normalized_keys["belegnummer"],
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_invoice_sequence_gaps_v1":
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE {_eq_normalized_sql('"Kreditor"')}
              AND {_eq_normalized_sql('"Belegnummer"')}
            ORDER BY "Belegnummer" {resolved_order_direction}
            LIMIT ?
        """
        params = [
            normalized_keys["kreditor"],
            normalized_keys["belegnummer"],
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_negative_quantity_receipts_v1":
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE {_eq_normalized_sql('"Kreditor"')}
              AND {_eq_normalized_sql('"Belegnummer"')}
              AND {_eq_normalized_sql('"Material"')}
            ORDER BY TRY_CAST("Menge" AS DOUBLE) ASC
            LIMIT ?
        """
        params = [
            normalized_keys["kreditor"],
            normalized_keys["belegnummer"],
            normalized_keys["material"],
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_duplicate_material_items_v1":
        kreditor_filter = normalized_keys.get("kreditor")
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE (? IS NULL OR {_eq_normalized_sql('"Kreditor"')})
              AND {_eq_normalized_sql('"Belegnummer"')}
              AND {_eq_normalized_sql('"Position"')}
              AND {_eq_normalized_sql('"Material"')}
            ORDER BY "Position" {resolved_order_direction}, "Material" {resolved_order_direction}
            LIMIT ?
        """
        params = [
            kreditor_filter,
            kreditor_filter,
            normalized_keys["belegnummer"],
            normalized_keys["position"],
            normalized_keys["material"],
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_unusual_posting_times_v1":
        if any(key not in {"Transaktionsart"} for key in filters.keys()):
            raise ValueError(
                "extra_filters no permitidos para unusual_posting_times; permitido: Transaktionsart"
            )
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE {_eq_normalized_sql('"Kreditor"')}
              AND {_eq_normalized_sql('"Belegnummer"')}
              AND TRIM(CAST("Erfassungsuhrzeit" AS VARCHAR)) = TRIM(CAST(? AS VARCHAR))
              AND (? IS NULL OR "Transaktionsart" = ?)
            ORDER BY "Erfassungsuhrzeit" {resolved_order_direction}, "Belegnummer" {resolved_order_direction}
            LIMIT ?
        """
        params = [
            normalized_keys["kreditor"],
            normalized_keys["belegnummer"],
            normalized_keys["erfassungsuhrzeit"],
            filters.get("Transaktionsart"),
            filters.get("Transaktionsart"),
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_large_even_dollar_entries_v1":
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE {_eq_normalized_sql('"Kreditor"')}
              AND {_eq_normalized_sql('"Belegnummer"')}
              AND ABS(TRY_CAST("Betrag" AS DOUBLE) - TRY_CAST(? AS DOUBLE)) < 1e-9
            ORDER BY TRY_CAST("Betrag" AS DOUBLE) {resolved_order_direction}
            LIMIT ?
        """
        params = [
            normalized_keys["kreditor"],
            normalized_keys["belegnummer"],
            normalized_keys["betrag"],
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_o2c_price_outlier_v1":
        table_ref = '"o2c"."o2c_order"'
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE sales_order_id = ?
              AND sales_order_item_id = ?
            LIMIT ?
        """
        params = [normalized_keys["sales_order_id"], normalized_keys["sales_order_item_id"], resolved_limit]
        return query, params

    if resolved_query_id == "drilldown_o2c_discount_policy_breach_v1":
        table_ref = '"o2c"."o2c_order"'
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE sales_order_id = ?
              AND sales_order_item_id = ?
            LIMIT ?
        """
        params = [normalized_keys["sales_order_id"], normalized_keys["sales_order_item_id"], resolved_limit]
        return query, params

    if resolved_query_id == "drilldown_o2c_delivery_quantity_mismatch_v1":
        table_ref = '"o2c"."o2c_delivery"'
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE delivery_id = ?
              AND delivery_item_id = ?
            LIMIT ?
        """
        params = [normalized_keys["delivery_id"], normalized_keys["delivery_item_id"], resolved_limit]
        return query, params

    if resolved_query_id == "drilldown_o2c_negative_delivery_quantity_v1":
        table_ref = '"o2c"."o2c_delivery"'
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE delivery_id = ?
              AND delivery_item_id = ?
            LIMIT ?
        """
        params = [normalized_keys["delivery_id"], normalized_keys["delivery_item_id"], resolved_limit]
        return query, params

    if resolved_query_id == "drilldown_o2c_clearing_anomaly_v1":
        table_ref = '"o2c"."o2c_collection"'
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE company_code = ?
              AND receivable_document_id = ?
              AND fiscal_year = ?
            LIMIT ?
        """
        params = [
            normalized_keys["company_code"],
            normalized_keys["receivable_document_id"],
            normalized_keys["fiscal_year"],
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_o2c_invoice_amount_anomaly_v1":
        table_ref = '"o2c"."o2c_invoice"'
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE company_code = ?
              AND accounting_document_id = ?
              AND fiscal_year = ?
            LIMIT ?
        """
        params = [
            normalized_keys["company_code"],
            normalized_keys["accounting_document_id"],
            normalized_keys["fiscal_year"],
            resolved_limit,
        ]
        return query, params

    if resolved_query_id == "drilldown_o2c_invoice_date_sequence_v1":
        table_ref = '"o2c"."o2c_invoice"'
        query = f"""
            SELECT *
            FROM {table_ref}
            WHERE company_code = ?
              AND accounting_document_id = ?
              AND fiscal_year = ?
            LIMIT ?
        """
        params = [
            normalized_keys["company_code"],
            normalized_keys["accounting_document_id"],
            normalized_keys["fiscal_year"],
            resolved_limit,
        ]
        return query, params

    raise KeyError(f"query_id no soportado para drilldown: {resolved_query_id}")


def drilldown(
    *,
    test_id: str,
    keys: dict[str, str],
    query_id: str | None = None,
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    schema_name: str = "main",
    table_name: str = "fraud_1",
    limit_rows: int = DEFAULT_DRILLDOWN_LIMIT,
    order_direction: str = "ASC",
    extra_filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Devuelve filas origen para un hallazgo usando SQL parametrizado seguro."""
    query, params = _build_drilldown_query_and_params(
        test_id=test_id,
        keys=keys,
        query_id=query_id,
        schema_name=schema_name,
        table_name=table_name,
        limit_rows=limit_rows,
        order_direction=order_direction,
        extra_filters=extra_filters,
    )

    conn = get_duckdb_connection(db_path)
    try:
        cur = conn.execute(query, params)
        columns = [str(col[0]) for col in cur.description]
        rows = cur.fetchall()
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({columns[idx]: row[idx] for idx in range(len(columns))})
    return out
