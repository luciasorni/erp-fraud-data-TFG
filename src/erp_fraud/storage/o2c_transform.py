"""Transformaciones raw -> canónico O2C en DuckDB (RF11-05)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb


class O2CTransformError(RuntimeError):
    """Error de transformación O2C."""


@dataclass(frozen=True)
class O2CEntityTransformStatus:
    entity: str
    status: str
    reason: str
    rows_loaded: int


def _load_yaml(path: str | Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise O2CTransformError("PyYAML no disponible para cargar config O2C") from exc
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"No existe config YAML: {cfg_path}")
    payload = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise O2CTransformError(f"Config inválida (raíz no objeto): {cfg_path}")
    return payload


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE lower(table_schema) = 'main' AND lower(table_name) = lower(?)
        LIMIT 1
        """,
        [table_name],
    ).fetchone()
    return bool(row)


def _entity_required_tables(schema_cfg: dict[str, Any], entity: str) -> list[str]:
    entities = schema_cfg.get("entities", {})
    if not isinstance(entities, dict):
        return []
    node = entities.get(entity, {})
    if not isinstance(node, dict):
        return []
    req = node.get("required_source_tables", [])
    if not isinstance(req, list):
        return []
    return [str(x).strip() for x in req if str(x).strip()]


def _degradation_sets(schema_cfg: dict[str, Any]) -> tuple[set[str], set[str]]:
    policy = schema_cfg.get("degradation_policy", {})
    if not isinstance(policy, dict):
        return set(), set()
    fail_fast = policy.get("fail_fast_entities", [])
    soft_fail = policy.get("soft_fail_entities", [])
    ff = {str(x).strip() for x in fail_fast if str(x).strip()} if isinstance(fail_fast, list) else set()
    sf = {str(x).strip() for x in soft_fail if str(x).strip()} if isinstance(soft_fail, list) else set()
    return ff, sf


def _q_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _create_or_replace_entity_table(
    conn: duckdb.DuckDBPyConnection,
    *,
    entity: str,
    target_schema: str,
    sql_body: str,
) -> int:
    target = f"{_q_ident(target_schema)}.{_q_ident(entity)}"
    conn.execute(f"CREATE OR REPLACE TABLE {target} AS {sql_body}")
    row = conn.execute(f"SELECT COUNT(*) FROM {target}").fetchone()
    return int(row[0] if row else 0)


def _build_order_sql() -> str:
    return """
    WITH base AS (
      SELECT
        CAST(vbak."VBELN" AS VARCHAR) AS sales_order_id,
        CAST(vbap."POSNR" AS VARCHAR) AS sales_order_item_id,
        CAST(COALESCE(vbak."KUNNR", vbpa."KUNNR") AS VARCHAR) AS customer_id,
        TRY_CAST(vbak."ERDAT" AS DATE) AS order_created_date,
        TRY_CAST(vbap."NETWR" AS DOUBLE) AS net_amount,
        CAST(vbak."VKORG" AS VARCHAR) AS sales_org,
        CAST(vbak."VTWEG" AS VARCHAR) AS distribution_channel,
        CAST(vbak."SPART" AS VARCHAR) AS division,
        CAST(vbap."MATNR" AS VARCHAR) AS material_id,
        TRY_CAST(vbap."KWMENG" AS DOUBLE) AS ordered_quantity,
        TRY_CAST(vbap."NETPR" AS DOUBLE) AS item_net_price,
        TRY_CAST(konv."KWERT" AS DOUBLE) AS condition_amount,
        CAST(kna1."KDGRP" AS VARCHAR) AS customer_group,
        (
          CASE WHEN COALESCE(vbak."KUNNR", vbpa."KUNNR") IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN vbak."ERDAT" IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN vbap."NETWR" IS NOT NULL THEN 1 ELSE 0 END
        ) AS quality_score
      FROM main."VBAP" vbap
      INNER JOIN main."VBAK" vbak ON vbap."VBELN" = vbak."VBELN"
      LEFT JOIN main."VBPA" vbpa
        ON vbpa."VBELN" = vbap."VBELN"
      LEFT JOIN main."KNA1" kna1
        ON kna1."KUNNR" = COALESCE(vbak."KUNNR", vbpa."KUNNR")
      LEFT JOIN main."KONV" konv
        ON konv."KNUMV" = vbak."KNUMV"
    ),
    ranked AS (
      SELECT
        *,
        ROW_NUMBER() OVER (
          PARTITION BY sales_order_id, sales_order_item_id
          ORDER BY quality_score DESC, sales_order_id, sales_order_item_id
        ) AS _rn
      FROM base
      WHERE sales_order_id IS NOT NULL AND sales_order_item_id IS NOT NULL
    )
    SELECT
      sales_order_id,
      sales_order_item_id,
      customer_id,
      order_created_date,
      net_amount,
      sales_org,
      distribution_channel,
      division,
      material_id,
      ordered_quantity,
      item_net_price,
      condition_amount,
      customer_group
    FROM ranked
    WHERE _rn = 1
    """


def _build_delivery_sql() -> str:
    return """
    WITH base AS (
      SELECT
        CAST(COALESCE(lips."VBELN", likp."VBELN") AS VARCHAR) AS delivery_id,
        CAST(lips."POSNR" AS VARCHAR) AS delivery_item_id,
        CAST(lips."VGBEL" AS VARCHAR) AS reference_sales_order_id,
        CAST(lips."VGPOS" AS VARCHAR) AS reference_sales_order_item_id,
        TRY_CAST(lips."LFIMG" AS DOUBLE) AS delivered_quantity,
        TRY_CAST(likp."LFDAT" AS DATE) AS delivery_date,
        TRY_CAST(likp."WADAT_IST" AS DATE) AS goods_issue_date,
        CAST(likp."KUNNR" AS VARCHAR) AS ship_to_customer_id,
        CAST(lips."MATNR" AS VARCHAR) AS material_id,
        CAST(lips."WERKS" AS VARCHAR) AS plant_id,
        (
          CASE WHEN lips."VGBEL" IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN lips."LFIMG" IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN likp."LFDAT" IS NOT NULL THEN 1 ELSE 0 END
        ) AS quality_score
      FROM main."LIPS" lips
      LEFT JOIN main."LIKP" likp
        ON lips."VBELN" = likp."VBELN"
    ),
    ranked AS (
      SELECT
        *,
        ROW_NUMBER() OVER (
          PARTITION BY delivery_id, delivery_item_id
          ORDER BY quality_score DESC, delivery_id, delivery_item_id
        ) AS _rn
      FROM base
      WHERE delivery_id IS NOT NULL AND delivery_item_id IS NOT NULL
    )
    SELECT
      delivery_id,
      delivery_item_id,
      reference_sales_order_id,
      reference_sales_order_item_id,
      delivered_quantity,
      delivery_date,
      goods_issue_date,
      ship_to_customer_id,
      material_id,
      plant_id
    FROM ranked
    WHERE _rn = 1
    """


def _build_invoice_sql() -> str:
    return """
    WITH base AS (
      SELECT
        CAST(COALESCE(bseg."BELNR", bkpf."BELNR") AS VARCHAR) AS accounting_document_id,
        CAST(COALESCE(bseg."GJAHR", bkpf."GJAHR") AS VARCHAR) AS fiscal_year,
        CAST(COALESCE(bseg."BUKRS", bkpf."BUKRS") AS VARCHAR) AS company_code,
        TRY_CAST(bkpf."BUDAT" AS DATE) AS posting_date,
        CAST(COALESCE(bseg."KUNNR", bseg."HKONT") AS VARCHAR) AS customer_or_account_id,
        TRY_CAST(bseg."DMBTR" AS DOUBLE) AS amount_local_currency,
        TRY_CAST(bseg."WRBTR" AS DOUBLE) AS document_currency_amount,
        CAST(bseg."SHKZG" AS VARCHAR) AS debit_credit_indicator,
        TRY_CAST(bseg."ZFBDT" AS DATE) AS baseline_date,
        CAST(bseg."AUGBL" AS VARCHAR) AS clearing_document_id,
        TRY_CAST(bseg."AUGDT" AS DATE) AS clearing_date,
        CAST(NULL AS VARCHAR) AS reference_delivery_id,
        (
          CASE WHEN bkpf."BUDAT" IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN bseg."DMBTR" IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN COALESCE(bseg."KUNNR", bseg."HKONT") IS NOT NULL THEN 1 ELSE 0 END
        ) AS quality_score
      FROM main."BSEG" bseg
      INNER JOIN main."BKPF" bkpf
        ON bseg."BUKRS" = bkpf."BUKRS"
       AND bseg."BELNR" = bkpf."BELNR"
       AND bseg."GJAHR" = bkpf."GJAHR"
    ),
    ranked AS (
      SELECT
        *,
        ROW_NUMBER() OVER (
          PARTITION BY company_code, accounting_document_id, fiscal_year
          ORDER BY quality_score DESC, accounting_document_id
        ) AS _rn
      FROM base
      WHERE accounting_document_id IS NOT NULL
        AND fiscal_year IS NOT NULL
        AND company_code IS NOT NULL
    )
    SELECT
      accounting_document_id,
      fiscal_year,
      company_code,
      posting_date,
      customer_or_account_id,
      amount_local_currency,
      document_currency_amount,
      debit_credit_indicator,
      baseline_date,
      clearing_document_id,
      clearing_date,
      reference_delivery_id
    FROM ranked
    WHERE _rn = 1
    """


def _build_collection_sql() -> str:
    return """
    WITH base AS (
      SELECT
        CAST(bseg."BELNR" AS VARCHAR) AS receivable_document_id,
        CAST(bseg."BUKRS" AS VARCHAR) AS company_code,
        CAST(bseg."GJAHR" AS VARCHAR) AS fiscal_year,
        CAST(bseg."KUNNR" AS VARCHAR) AS customer_id,
        TRY_CAST(bseg."DMBTR" AS DOUBLE) AS amount_local_currency,
        CAST(bseg."AUGBL" AS VARCHAR) AS clearing_document_id,
        TRY_CAST(bseg."AUGDT" AS DATE) AS clearing_date,
        CAST(bseg."ZTERM" AS VARCHAR) AS payment_terms,
        TRY_CAST(bseg."ZFBDT" AS DATE) AS baseline_date,
        TRY_CAST(bkpf."BUDAT" AS DATE) AS posting_date,
        (
          CASE WHEN bseg."AUGBL" IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN bseg."AUGDT" IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN bseg."KUNNR" IS NOT NULL THEN 1 ELSE 0 END
        ) AS quality_score
      FROM main."BSEG" bseg
      LEFT JOIN main."BKPF" bkpf
        ON bseg."BUKRS" = bkpf."BUKRS"
       AND bseg."BELNR" = bkpf."BELNR"
       AND bseg."GJAHR" = bkpf."GJAHR"
    ),
    ranked AS (
      SELECT
        *,
        ROW_NUMBER() OVER (
          PARTITION BY company_code, receivable_document_id, fiscal_year
          ORDER BY quality_score DESC, receivable_document_id
        ) AS _rn
      FROM base
      WHERE receivable_document_id IS NOT NULL
        AND company_code IS NOT NULL
        AND fiscal_year IS NOT NULL
    )
    SELECT
      receivable_document_id,
      company_code,
      fiscal_year,
      customer_id,
      amount_local_currency,
      clearing_document_id,
      clearing_date,
      payment_terms,
      baseline_date,
      posting_date
    FROM ranked
    WHERE _rn = 1
    """


def _build_customer_sql() -> str:
    return """
    WITH base AS (
      SELECT
        CAST(kna1."KUNNR" AS VARCHAR) AS customer_id,
        CAST(kna1."NAME1" AS VARCHAR) AS customer_name,
        CAST(kna1."LAND1" AS VARCHAR) AS country,
        CAST(kna1."ORT01" AS VARCHAR) AS city,
        CAST(kna1."KTOKD" AS VARCHAR) AS account_group,
        CAST(knb1."AKONT" AS VARCHAR) AS reconciliation_account,
        CAST(knb1."ZTERM" AS VARCHAR) AS payment_terms,
        CAST(knb1."MAHNA" AS VARCHAR) AS dunning_procedure,
        (
          CASE WHEN kna1."NAME1" IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN kna1."LAND1" IS NOT NULL THEN 1 ELSE 0 END +
          CASE WHEN kna1."ORT01" IS NOT NULL THEN 1 ELSE 0 END
        ) AS quality_score
      FROM main."KNA1" kna1
      LEFT JOIN main."KNB1" knb1
        ON kna1."KUNNR" = knb1."KUNNR"
    ),
    ranked AS (
      SELECT
        *,
        ROW_NUMBER() OVER (
          PARTITION BY customer_id
          ORDER BY quality_score DESC, customer_id
        ) AS _rn
      FROM base
      WHERE customer_id IS NOT NULL
    )
    SELECT
      customer_id,
      customer_name,
      country,
      city,
      account_group,
      reconciliation_account,
      payment_terms,
      dunning_procedure
    FROM ranked
    WHERE _rn = 1
    """


_ENTITY_SQL_BUILDERS: dict[str, Any] = {
    "o2c_order": _build_order_sql,
    "o2c_delivery": _build_delivery_sql,
    "o2c_invoice": _build_invoice_sql,
    "o2c_collection": _build_collection_sql,
    "o2c_customer": _build_customer_sql,
}


def transform_raw_to_o2c_canonical(
    *,
    conn: duckdb.DuckDBPyConnection,
    canonical_schema_config_path: str | Path = "config/canonical_schema_o2c.yaml",
    identity_config_path: str | Path = "config/o2c_entity_identity.yaml",
    mapping_config_path: str | Path = "config/column_mapping_o2c.yaml",
    target_schema: str = "o2c",
) -> dict[str, Any]:
    """Construye tablas canónicas O2C en DuckDB a partir de tablas raw ya cargadas.

    Esta función no carga `raw_data` desde zip; asume tablas SAP (`VBAK`, `VBAP`, etc.)
    disponibles en `main`.
    """
    schema_cfg = _load_yaml(canonical_schema_config_path)
    _load_yaml(identity_config_path)  # validar existencia/sintaxis para RF11-04
    mapping_cfg = _load_yaml(mapping_config_path)  # validar existencia/sintaxis para RF11-09

    entities = list(_ENTITY_SQL_BUILDERS.keys())
    mapping_entities = mapping_cfg.get("entities", {})
    if not isinstance(mapping_entities, dict):
        raise O2CTransformError("column_mapping_o2c.yaml inválido: 'entities' debe ser objeto")
    missing_mapping_entities = [entity for entity in entities if entity not in mapping_entities]
    if missing_mapping_entities:
        raise O2CTransformError(
            "column_mapping_o2c.yaml incompleto, faltan entidades: "
            + ", ".join(sorted(missing_mapping_entities))
        )
    fail_fast_entities, soft_fail_entities = _degradation_sets(schema_cfg)

    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {_q_ident(target_schema)}")

    statuses: list[O2CEntityTransformStatus] = []

    for entity in entities:
        req_tables = _entity_required_tables(schema_cfg, entity)
        missing_required = [t for t in req_tables if not _table_exists(conn, t)]
        if missing_required:
            reason = f"Missing required source tables: {', '.join(sorted(missing_required))}"
            if entity in fail_fast_entities:
                raise O2CTransformError(f"{entity}: {reason}")
            if entity in soft_fail_entities:
                statuses.append(
                    O2CEntityTransformStatus(
                        entity=entity,
                        status="SKIPPED",
                        reason=reason,
                        rows_loaded=0,
                    )
                )
                continue
            # Default conservador si no está en ninguna lista.
            raise O2CTransformError(f"{entity}: {reason}")

        sql_builder = _ENTITY_SQL_BUILDERS.get(entity)
        if sql_builder is None:
            statuses.append(O2CEntityTransformStatus(entity=entity, status="SKIPPED", reason="No SQL builder", rows_loaded=0))
            continue

        rows = _create_or_replace_entity_table(
            conn,
            entity=entity,
            target_schema=target_schema,
            sql_body=str(sql_builder()),
        )
        statuses.append(
            O2CEntityTransformStatus(
                entity=entity,
                status="OK",
                reason="",
                rows_loaded=rows,
            )
        )

    return {
        "target_schema": target_schema,
        "entities_total": len(entities),
        "entities_ok": sum(1 for s in statuses if s.status == "OK"),
        "entities_skipped": sum(1 for s in statuses if s.status == "SKIPPED"),
        "entity_status": [
            {
                "entity": s.entity,
                "status": s.status,
                "reason": s.reason,
                "rows_loaded": s.rows_loaded,
            }
            for s in statuses
        ],
        "identity_config_path": str(identity_config_path),
        "canonical_schema_config_path": str(canonical_schema_config_path),
        "mapping_config_path": str(mapping_config_path),
    }
