from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from src.erp_fraud.catalog.drilldown import drilldown
from src.erp_fraud.catalog.drilldown_templates import get_drilldown_query_id_for_test_id
from src.erp_fraud.cli.main import _safe_table_name_from_file
from src.erp_fraud.ingest import cargar_fichero_tabular_desde_zip, limpiar_tecnicamente_dataframe, listar_ficheros_joint_datasets, normalizar_tipos_dataframe, validar_ficheros_esperados_joint_datasets
from src.erp_fraud.storage import get_duckdb_connection, load_table_to_duckdb_with_stats
from src.erp_fraud.storage.o2c_transform import transform_raw_to_o2c_canonical

from ..schemas.drilldown import DrilldownRequest, DrilldownResponse
from .aws_service import AWSAPISettings, create_s3_client
from .datasets_service import get_dataset
from .runs_service import get_run


ALLOWED_DRILLDOWN_ACTIONS = ("finding_rows",)


def _cache_root() -> Path:
    return Path(tempfile.gettempdir()) / "erp_fraud_api_drilldown_cache"


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
    settings: AWSAPISettings,
    s3_client: Any,
) -> tuple[Path, str, str]:
    cache_dir = _cache_root() / dataset_id / scope
    cache_dir.mkdir(parents=True, exist_ok=True)
    db_path = cache_dir / "erp.duckdb"
    if db_path.exists():
        if scope == "o2c":
            return db_path, "o2c", "o2c_order"
        return db_path, "main", "fraud_1"

    zip_path = _download_dataset_zip(dataset_key=dataset_key, settings=settings, s3_client=s3_client)
    validar_ficheros_esperados_joint_datasets(zip_path)
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
    if scope == "o2c":
        with get_duckdb_connection(db_path) as conn:
            transform_raw_to_o2c_canonical(conn=conn, target_schema="o2c")
        return db_path, "o2c", "o2c_order"
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
        settings=settings,
        s3_client=client,
    )
    if status_callback:
        status_callback(stage="querying", message="Ejecutando drilldown sobre evidencia del hallazgo...", progress=75)
    rows = drilldown(
        test_id=payload.test_id,
        schema_name=schema_name,
        table_name=table_name,
        db_path=db_path,
        keys=payload.keys,
        limit_rows=payload.limit_rows,
        order_direction=payload.order_direction,
        extra_filters=payload.extra_filters,
    )
    response = DrilldownResponse(
        run_id=run_id,
        action=payload.action,
        test_id=payload.test_id,
        query_id=get_drilldown_query_id_for_test_id(payload.test_id),
        row_count=len(rows),
        rows=rows,
        allowed_actions=list(ALLOWED_DRILLDOWN_ACTIONS),
    )
    if status_callback:
        status_callback(stage="completed", message="Drilldown completado.", progress=100)
    return response
