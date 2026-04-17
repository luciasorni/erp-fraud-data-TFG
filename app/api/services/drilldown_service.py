from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from src.erp_fraud.catalog.drilldown import drilldown
from src.erp_fraud.catalog.drilldown_keys import normalize_drilldown_keys, validate_minimum_keys_for_test_id
from src.erp_fraud.catalog.drilldown_templates import get_drilldown_query_id_for_test_id
from src.erp_fraud.cli.main import (
    _ensure_o2c_optional_placeholders,
    _load_o2c_raw_tables_from_zip_if_needed,
    _safe_table_name_from_file,
)
from src.erp_fraud.ingest import cargar_fichero_tabular_desde_zip, limpiar_tecnicamente_dataframe, listar_ficheros_joint_datasets, normalizar_tipos_dataframe, validar_ficheros_esperados_joint_datasets
from src.erp_fraud.storage import get_duckdb_connection, load_table_to_duckdb_with_stats
from src.erp_fraud.storage.o2c_transform import (
    _create_or_replace_entity_table,
    _entity_required_tables,
    _ENTITY_SQL_BUILDERS,
    _load_yaml,
    _q_ident,
    transform_raw_to_o2c_canonical,
)

from ..schemas.drilldown import DrilldownRequest, DrilldownResponse
from .aws_service import AWSAPISettings, create_s3_client
from .datasets_service import get_dataset
from .runs_service import get_run


ALLOWED_DRILLDOWN_ACTIONS = ("finding_rows",)


def _resolve_query_id(*, test_id: str, query_id: str | None) -> str:
    explicit = str(query_id or "").strip()
    if explicit:
        return explicit
    try:
        return get_drilldown_query_id_for_test_id(test_id)
    except KeyError as exc:
        raise ValueError(
            f"El finding no trae drilldown_template ni se pudo resolver query_id para test_id={test_id}"
        ) from exc


def _cache_root() -> Path:
    return Path(tempfile.gettempdir()) / "erp_fraud_api_drilldown_cache"


def _required_o2c_tables_for_query_id(query_id: str | None) -> set[str]:
    value = str(query_id or "").strip()
    if value in {
        "drilldown_o2c_delivery_quantity_mismatch_v1",
        "drilldown_o2c_negative_delivery_quantity_v1",
    }:
        return {"o2c_delivery"}
    if value in {"drilldown_o2c_price_outlier_v1", "drilldown_o2c_discount_policy_breach_v1"}:
        return {"o2c_order"}
    if value in {"drilldown_o2c_clearing_anomaly_v1"}:
        return {"o2c_collection"}
    if value in {
        "drilldown_o2c_invoice_amount_anomaly_v1",
        "drilldown_o2c_invoice_date_sequence_v1",
    }:
        return {"o2c_invoice"}
    return set()


def _required_o2c_entities_for_query_id(query_id: str | None) -> list[str]:
    return sorted(_required_o2c_tables_for_query_id(query_id))


def _required_o2c_raw_tables_for_query_id(
    *,
    query_id: str | None,
    canonical_schema_config_path: str | Path = "config/canonical_schema_o2c.yaml",
) -> list[str]:
    required_entities = _required_o2c_entities_for_query_id(query_id)
    if not required_entities:
        return []
    schema_cfg = _load_yaml(canonical_schema_config_path)
    tables: set[str] = set()
    for entity in required_entities:
        for table_name in _entity_required_tables(schema_cfg, entity):
            normalized = str(table_name).strip().upper()
            if normalized:
                tables.add(normalized)
    return sorted(tables)


def _duckdb_table_exists(*, db_path: Path, schema_name: str, table_name: str) -> bool:
    with get_duckdb_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE lower(table_schema) = lower(?)
              AND lower(table_name) = lower(?)
            LIMIT 1
            """,
            [schema_name, table_name],
        ).fetchone()
    return bool(row)


def _conn_table_exists(*, conn: Any, schema_name: str, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE lower(table_schema) = lower(?)
          AND lower(table_name) = lower(?)
        LIMIT 1
        """,
        [schema_name, table_name],
    ).fetchone()
    return bool(row)


def _ensure_required_o2c_entities(
    *,
    db_path: Path,
    target_schema: str,
    query_id: str | None,
    canonical_schema_config_path: str | Path = "config/canonical_schema_o2c.yaml",
) -> None:
    required_entities = _required_o2c_entities_for_query_id(query_id)
    if not required_entities:
        with get_duckdb_connection(db_path) as conn:
            transform_raw_to_o2c_canonical(conn=conn, target_schema=target_schema)
        return

    schema_cfg = _load_yaml(canonical_schema_config_path)
    with get_duckdb_connection(db_path) as conn:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {_q_ident(target_schema)}")
        for entity in required_entities:
            if _conn_table_exists(conn=conn, schema_name=target_schema, table_name=entity):
                continue
            required_raw_tables = _entity_required_tables(schema_cfg, entity)
            missing_required = [
                table for table in required_raw_tables if not _conn_table_exists(conn=conn, schema_name="main", table_name=table)
            ]
            if missing_required:
                raise ValueError(
                    f"No se puede construir {entity} para drilldown: faltan tablas raw requeridas {', '.join(sorted(missing_required))}"
                )
            sql_builder = _ENTITY_SQL_BUILDERS.get(entity)
            if sql_builder is None:
                raise ValueError(f"No existe builder canónico O2C para la entidad {entity}")
            _create_or_replace_entity_table(
                conn,
                entity=entity,
                target_schema=target_schema,
                sql_body=str(sql_builder()),
            )


def _download_dataset_zip(
    *,
    dataset_key: str,
    settings: AWSAPISettings,
    s3_client: Any,
) -> Path:
    from src.erp_fraud.storage import parse_s3_uri

    bucket, _ = parse_s3_uri(settings.s3_input_uri, allow_empty_prefix=True)
    local_root = _cache_root() / "datasets"
    local_root.mkdir(parents=True, exist_ok=True)
    local_zip = local_root / Path(dataset_key).parts[-2] / "erp_fraud_data.zip"
    local_zip.parent.mkdir(parents=True, exist_ok=True)
    if not local_zip.exists():
        s3_client.download_file(bucket, dataset_key, str(local_zip))
    return local_zip


def _build_db_cache(
    *,
    dataset_id: str,
    scope: str,
    dataset_key: str,
    query_id: str | None,
    settings: AWSAPISettings,
    s3_client: Any,
) -> tuple[Path, str, str]:
    cache_dir = _cache_root() / dataset_id / scope
    cache_dir.mkdir(parents=True, exist_ok=True)
    db_path = cache_dir / "erp.duckdb"
    if db_path.exists():
        if scope == "o2c":
            required_tables = _required_o2c_tables_for_query_id(query_id)
            if required_tables and not all(
                _duckdb_table_exists(db_path=db_path, schema_name="o2c", table_name=table_name)
                for table_name in required_tables
            ):
                try:
                    _ensure_required_o2c_entities(db_path=db_path, target_schema="o2c", query_id=query_id)
                except ValueError:
                    db_path.unlink(missing_ok=True)
                else:
                    return db_path, "o2c", "o2c_order"
            else:
                return db_path, "o2c", "o2c_order"
        else:
            return db_path, "main", "fraud_1"

    zip_path = _download_dataset_zip(dataset_key=dataset_key, settings=settings, s3_client=s3_client)
    validar_ficheros_esperados_joint_datasets(zip_path)
    if scope == "o2c":
        required_raw_tables = _required_o2c_raw_tables_for_query_id(query_id=query_id)
        with get_duckdb_connection(db_path) as conn:
            _load_o2c_raw_tables_from_zip_if_needed(
                conn=conn,
                zip_path=str(zip_path),
                canonical_schema_config_path="config/canonical_schema_o2c.yaml",
                target_tables=required_raw_tables,
            )
            _ensure_o2c_optional_placeholders(conn)
        _ensure_required_o2c_entities(db_path=db_path, target_schema="o2c", query_id=query_id)
        required_tables = _required_o2c_tables_for_query_id(query_id)
        missing_tables = [
            table_name
            for table_name in required_tables
            if not _duckdb_table_exists(db_path=db_path, schema_name="o2c", table_name=table_name)
        ]
        if missing_tables:
            raise ValueError(
                "La cache O2C no contiene las tablas canónicas necesarias para drilldown: "
                + ", ".join(sorted(missing_tables))
            )
        return db_path, "o2c", "o2c_order"
    files = listar_ficheros_joint_datasets(zip_path)
    for file_name in files:
        suffix = Path(file_name).suffix.lower()
        if suffix not in {".csv", ".parquet"}:
            continue
        table_name = _safe_table_name_from_file(file_name)
        df = cargar_fichero_tabular_desde_zip(zip_path, file_name)
        df, _ = normalizar_tipos_dataframe(df, fail_on_parse_errors=False)
        df, _ = limpiar_tecnicamente_dataframe(df)
        load_table_to_duckdb_with_stats(
            table_name=table_name,
            df=df,
            mode="overwrite",
            db_path=db_path,
        )
    return db_path, "main", "fraud_1"


def execute_drilldown(
    *,
    run_id: str,
    payload: DrilldownRequest,
    settings: AWSAPISettings,
    s3_client: Any | None = None,
    status_callback: Any | None = None,
) -> DrilldownResponse:
    if payload.action not in ALLOWED_DRILLDOWN_ACTIONS:
        raise ValueError(f"action no permitida: {payload.action}")
    normalized_keys = normalize_drilldown_keys(payload.keys)
    if not normalized_keys:
        raise ValueError(f"El hallazgo no trae keys válidas para ejecutar drilldown en test_id={payload.test_id}")
    validate_minimum_keys_for_test_id(payload.test_id, normalized_keys)
    query_id = _resolve_query_id(test_id=payload.test_id, query_id=payload.query_id)
    client = s3_client or create_s3_client(settings=settings)
    if status_callback:
        status_callback(stage="loading_run", message="Cargando contexto del run...", progress=10)
    run = get_run(run_id=run_id, settings=settings, s3_client=client)
    if run is None:
        raise ValueError(f"run_id no encontrado: {run_id}")
    if not run.dataset_id:
        raise ValueError(f"run_id sin dataset_id registrado: {run_id}")
    if run.scope not in {"p2p", "o2c"}:
        raise ValueError(f"scope no soportado para drilldown: {run.scope}")
    dataset = get_dataset(dataset_id=run.dataset_id, settings=settings, s3_client=client)
    if dataset is None:
        raise ValueError(f"dataset_id no encontrado: {run.dataset_id}")
    dataset_key = dataset.s3_keys.get(run.scope)
    if not dataset_key:
        raise ValueError(f"dataset_id {run.dataset_id} no tiene ZIP para scope={run.scope}")
    if status_callback:
        status_callback(stage="building_cache", message="Preparando cache analítica para drilldown...", progress=35)
    db_path, schema_name, table_name = _build_db_cache(
        dataset_id=run.dataset_id,
        scope=run.scope,
        dataset_key=dataset_key,
        query_id=query_id,
        settings=settings,
        s3_client=client,
    )
    if status_callback:
        status_callback(stage="querying", message="Ejecutando drilldown sobre evidencia del hallazgo...", progress=75)
    rows = drilldown(
        test_id=payload.test_id,
        query_id=query_id,
        schema_name=schema_name,
        table_name=table_name,
        db_path=db_path,
        keys=normalized_keys,
        limit_rows=payload.limit_rows,
        order_direction=payload.order_direction,
        extra_filters=payload.extra_filters,
    )
    response = DrilldownResponse(
        run_id=run_id,
        action=payload.action,
        test_id=payload.test_id,
        query_id=query_id,
        row_count=len(rows),
        rows=rows,
        allowed_actions=list(ALLOWED_DRILLDOWN_ACTIONS),
    )
    if status_callback:
        status_callback(stage="completed", message="Drilldown completado.", progress=100)
    return response
