"""CLI principal del proyecto ERP Fraud."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any
from zipfile import BadZipFile, ZipFile

import pandas as pd

from ..catalog import (
    CatalogValidationError,
    TestRunner,
    aggregate_findings_by_entity,
    drilldown,
    load_weights_config,
    parse_entity_key,
    resolve_ranking_top_k,
    validate_catalog_against_schema_summary,
    write_ranking_outputs,
    write_test_results_by_test_id,
)
from ..catalog.test_spec_loader import load_test_specs_from_catalog
from ..agents.kb_index import build_kb_index
from ..agents.kb_sources import load_kb_sources_config
from ..ingest import (
    calcular_dataset_hash,
    cargar_fichero_tabular_desde_zip,
    limpiar_tecnicamente_dataframe,
    listar_ficheros_joint_datasets,
    normalizar_tipos_dataframe,
    validar_ficheros_esperados_joint_datasets,
)
from ..storage import (
    IngestJsonLogger,
    RunOutputValidationError,
    download_s3_prefix_to_local_dir,
    download_required_inputs,
    get_duckdb_connection,
    load_table_to_duckdb_with_stats,
    parse_s3_uri,
    read_last_artifact_hash_state,
    run_technical_validation_before_tests,
    upload_run_outputs,
    write_last_artifact_hash_state,
    write_or_update_report_markdown_with_data_validation,
    write_or_update_report_markdown_with_drilldown_instructions,
    write_report_json,
    write_report_markdown_from_report_json,
    render_report_markdown_to_html,
    validate_report_artifact_paths_exist,
    validate_required_run_outputs,
    write_run_metadata_json,
    write_schema_summary_json,
    compute_artifact_hash,
)
from ..storage.o2c_transform import O2CTransformError, transform_raw_to_o2c_canonical
from ..storage.o2c_validation import write_o2c_validation_report_json
from ..storage.data_dictionary import DataDictionaryCompletenessError, check_dictionary_completeness
from ..storage.paths import ruta_run
from ..storage.report_json import build_report_json_payload
from ..storage.runs_comparison import (
    compare_runs,
    list_runs,
    pick_latest_run_ids_by_process_family,
    write_comparison_outputs,
)
from ..graph import run_graph_full
from ..config import (
    DEFAULT_CATALOG_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_KB_CHROMA_CONFIG,
    DEFAULT_KB_CHUNKING_CONFIG,
    DEFAULT_KB_ENABLED,
    DEFAULT_KB_SOURCES_CONFIG,
    DEFAULT_OUT_DIR,
    DEFAULT_O2C_CANONICAL_SCHEMA_CONFIG,
    DEFAULT_O2C_IDENTITY_CONFIG,
    DEFAULT_O2C_MAPPING_CONFIG,
    DEFAULT_O2C_TARGET_SCHEMA,
    DEFAULT_PROCESS_FAMILY,
    DEFAULT_RUN_INPUT_ZIP,
    DEFAULT_SAMPLE_TOP_N,
    DEFAULT_SCHEMA_NAME,
    DEFAULT_TABLE_NAME,
    DEFAULT_WEIGHTS_CONFIG,
)
from ..config.env import get_cloud_env_settings, validate_process_scope


def _run_validate_dictionary(args: argparse.Namespace) -> int:
    dictionary_path = Path(args.dictionary)
    if not dictionary_path.exists():
        print(f"ERROR: No existe dictionary JSON: {dictionary_path}", file=sys.stderr)
        return 2

    try:
        dictionary = json.loads(dictionary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: No se pudo leer/parsear el dictionary JSON: {exc}", file=sys.stderr)
        return 2

    try:
        summary = check_dictionary_completeness(
            dictionary,
            catalog_path=args.catalog,
        )
    except DataDictionaryCompletenessError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.output_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "OK: dictionary completo "
            f"(tests={summary['tests_analyzed']}, "
            f"referenced_unique={summary['referenced_fields_unique']}, "
            f"documented={summary['documented_fields_total']})"
        )
    return 0


def _utc_timestamp_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_drilldown(args: argparse.Namespace) -> int:
    try:
        keys = parse_entity_key(args.entity_key)
    except Exception as exc:
        print(f"ERROR: entity_key inválido: {exc}", file=sys.stderr)
        return 2

    extra_filters: dict[str, str] = {}
    if args.transaktionsart:
        extra_filters["Transaktionsart"] = str(args.transaktionsart)

    try:
        rows = drilldown(
            test_id=args.test_id,
            keys=keys,
            db_path=args.db_path,
            schema_name=args.schema_name,
            table_name=args.table_name,
            limit_rows=int(args.limit_rows),
            order_direction=str(args.order_direction).upper(),
            extra_filters=extra_filters or None,
        )
    except Exception as exc:
        print(f"ERROR: no se pudo ejecutar drilldown: {exc}", file=sys.stderr)
        return 1

    payload = {
        "generated_at_utc": _utc_timestamp_iso(),
        "run_id": args.run_id,
        "test_id": args.test_id,
        "entity_key": args.entity_key,
        "keys": keys,
        "row_count": len(rows),
        "rows": rows,
    }

    output_path: Path | None = None
    if args.output:
        output_path = Path(args.output)
    elif args.save_default:
        safe_test_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in args.test_id)
        output_path = ruta_run(args.run_id) / f"drilldown_{safe_test_id}.json"

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"OK: drilldown rows={len(rows)} saved={output_path}")
        return 0

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"run-{stamp}"


def _run_list_runs(args: argparse.Namespace) -> int:
    rows = list_runs(base_dir=args.base_dir)
    if args.output_json:
        print(json.dumps({"runs": rows, "count": len(rows)}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"Runs encontrados: {len(rows)}")
    for row in rows:
        run_id = str(row.get("run_id", ""))
        process_family = str(row.get("process_family", ""))
        llm_mode = str(row.get("llm_mode", ""))
        findings_total = int(row.get("findings_total", 0) or 0)
        selected_tests_count = int(row.get("selected_tests_count", 0) or 0)
        final_label = str(row.get("final_label", ""))
        confidence = float(row.get("confidence", 0.0) or 0.0)
        print(
            f"- {run_id} | family={process_family} | llm={llm_mode} | "
            f"selected_tests={selected_tests_count} | findings={findings_total} | "
            f"label={final_label} ({confidence:.2f})"
        )
    return 0


def _run_compare_runs(args: argparse.Namespace) -> int:
    run_ids = [str(item).strip() for item in (args.run_ids or []) if str(item).strip()]
    if not run_ids and args.auto_latest_p2p_o2c:
        run_ids = pick_latest_run_ids_by_process_family(base_dir=args.base_dir)
    if not run_ids:
        print("ERROR: Debes indicar run_ids o usar --auto-latest-p2p-o2c", file=sys.stderr)
        return 2

    try:
        payload = compare_runs(run_ids=run_ids, base_dir=args.base_dir)
    except Exception as exc:
        print(f"ERROR: compare-runs falló: {exc}", file=sys.stderr)
        return 1

    analysis_id = str(args.analysis_id).strip() if args.analysis_id else ""
    if not analysis_id:
        analysis_id = f"rf16-second-level-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    output_dir = Path(args.base_dir) / analysis_id
    output_json = output_dir / "rf16_second_level_analysis.json"
    output_md = output_dir / "rf16_second_level_analysis.md"
    write_comparison_outputs(
        payload=payload,
        output_json_path=output_json,
        output_md_path=output_md,
    )

    print(f"OK: compare-runs analysis_id={analysis_id}")
    print(f"- compared_runs: {', '.join(run_ids)}")
    print(f"- output_json: {output_json}")
    print(f"- output_md: {output_md}")
    print(f"- recommendations: {len(payload.get('recommendations', []))}")
    return 0


def _safe_table_name_from_file(file_name: str) -> str:
    stem = Path(file_name).stem.strip()
    if not stem:
        raise ValueError(f"Nombre de fichero inválido para tabla: {file_name}")
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in stem)


def _raw_data_nested_archives(zip_path: str | Path) -> list[str]:
    try:
        with ZipFile(zip_path) as zf:
            return sorted(
                name
                for name in zf.namelist()
                if name.lower().endswith(".zip") and "/raw_data/" in name.lower()
            )
    except BadZipFile as exc:
        raise RuntimeError(f"Zip corrupto o no válido: {zip_path}") from exc


def _raw_table_name_from_member(member_name: str) -> str:
    base = Path(member_name).name
    stem = Path(base).stem.strip()
    if not stem:
        return ""
    normalized = re.sub(r"_[0-9]+$", "", stem)
    return normalized.upper()


def _load_raw_member_dataframe(member_name: str, raw_bytes: bytes) -> pd.DataFrame:
    suffix = Path(member_name).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        try:
            df = pd.read_excel(io.BytesIO(raw_bytes), dtype="string")
        except ImportError as exc:
            raise RuntimeError(
                "missing_dependency_openpyxl: instala openpyxl en tu entorno activo"
            ) from exc
    elif suffix == ".csv":
        from ..ingest.tabular_loader import _leer_csv_bytes  # type: ignore

        df = _leer_csv_bytes(raw_bytes, dtype="string")
    elif suffix == ".parquet":
        from ..ingest.tabular_loader import _leer_parquet_bytes  # type: ignore

        df = _leer_parquet_bytes(raw_bytes)
    else:
        raise ValueError(f"Formato no soportado: {member_name}")
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _table_exists_in_main(conn: Any, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE lower(table_schema) = 'main'
          AND lower(table_name) = lower(?)
        LIMIT 1
        """,
        [table_name],
    ).fetchone()
    return bool(row)


def _load_yaml_config(path: str | Path) -> dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"No existe config YAML: {cfg_path}")
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise RuntimeError("PyYAML no disponible para cargar config O2C") from exc
    payload = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"Config YAML inválida (raíz no objeto): {cfg_path}")
    return payload


def _resolve_o2c_source_tables_from_config(canonical_schema_config_path: str | Path) -> list[str]:
    cfg = _load_yaml_config(canonical_schema_config_path)
    entities = cfg.get("entities", {})
    if not isinstance(entities, dict):
        return []
    tables: set[str] = set()
    for entity_cfg in entities.values():
        if not isinstance(entity_cfg, dict):
            continue
        for key in ("required_source_tables", "source_tables_preferred"):
            rows = entity_cfg.get(key, [])
            if isinstance(rows, list):
                for row in rows:
                    name = str(row).strip().upper()
                    if name:
                        tables.add(name)
    return sorted(tables)


def _resolve_o2c_fail_fast_required_tables(canonical_schema_config_path: str | Path) -> list[str]:
    cfg = _load_yaml_config(canonical_schema_config_path)
    policy = cfg.get("degradation_policy", {})
    entities_cfg = cfg.get("entities", {})
    if not isinstance(policy, dict) or not isinstance(entities_cfg, dict):
        return []
    fail_fast_entities = policy.get("fail_fast_entities", [])
    if not isinstance(fail_fast_entities, list):
        return []
    tables: set[str] = set()
    for entity_name in fail_fast_entities:
        node = entities_cfg.get(str(entity_name), {})
        if not isinstance(node, dict):
            continue
        required = node.get("required_source_tables", [])
        if isinstance(required, list):
            for table_name in required:
                normalized = str(table_name).strip().upper()
                if normalized:
                    tables.add(normalized)
    return sorted(tables)


def _load_o2c_raw_tables_from_zip_if_needed(
    *,
    conn: Any,
    zip_path: str,
    canonical_schema_config_path: str,
) -> dict[str, Any]:
    source_tables = _resolve_o2c_source_tables_from_config(canonical_schema_config_path)
    fail_fast_required_tables = _resolve_o2c_fail_fast_required_tables(canonical_schema_config_path)
    target_tables = fail_fast_required_tables or source_tables
    if not source_tables:
        return {
            "status": "SKIPPED",
            "reason": "no_source_tables_defined",
            "source_tables": [],
            "target_tables": [],
            "tables_loaded": [],
            "tables_already_present": [],
            "tables_missing_after_load": [],
            "nested_archives_count": 0,
        }

    missing_before = [table for table in target_tables if not _table_exists_in_main(conn, table)]
    if not missing_before:
        return {
            "status": "SKIPPED",
            "reason": "all_source_tables_already_present",
            "source_tables": source_tables,
            "target_tables": target_tables,
            "tables_loaded": [],
            "tables_already_present": target_tables,
            "tables_missing_after_load": [],
            "nested_archives_count": 0,
        }

    nested_archives = _raw_data_nested_archives(zip_path)
    if not nested_archives:
        return {
            "status": "SKIPPED",
            "reason": "raw_data_nested_archives_not_found",
            "source_tables": source_tables,
            "target_tables": target_tables,
            "tables_loaded": [],
            "tables_already_present": [t for t in target_tables if t not in missing_before],
            "tables_missing_after_load": missing_before,
            "nested_archives_count": 0,
        }

    supported_suffixes = {".xlsx", ".xls", ".csv", ".parquet"}
    aggregated: dict[str, list[pd.DataFrame]] = {}
    read_errors: list[str] = []
    invalid_nested_archives: list[str] = []
    loaded_members_count = 0

    with ZipFile(zip_path) as outer:
        for nested_name in nested_archives:
            print(f"[O2C autoload] scanning nested archive: {nested_name}", flush=True)
            try:
                nested_bytes = outer.read(nested_name)
            except KeyError:
                continue
            try:
                with ZipFile(io.BytesIO(nested_bytes)) as inner:
                    for member in sorted(inner.namelist()):
                        if member.endswith("/"):
                            continue
                        suffix = Path(member).suffix.lower()
                        if suffix not in supported_suffixes:
                            continue
                        table_name = _raw_table_name_from_member(member)
                        if table_name not in missing_before:
                            continue
                        try:
                            raw_bytes = inner.read(member)
                            df = _load_raw_member_dataframe(member, raw_bytes)
                        except Exception as exc:
                            read_errors.append(
                                f"{nested_name}:{member}:{type(exc).__name__}:{str(exc)}"
                            )
                            continue
                        if df.empty:
                            continue
                        aggregated.setdefault(table_name, []).append(df)
                        loaded_members_count += 1
            except BadZipFile:
                invalid_nested_archives.append(nested_name)
                continue

    loaded_tables: list[str] = []
    for table_name in sorted(aggregated.keys()):
        print(f"[O2C autoload] loading table: {table_name}", flush=True)
        frames = aggregated[table_name]
        combined = pd.concat(frames, ignore_index=True, sort=False)
        combined.columns = [str(col).strip() for col in combined.columns]
        load_table_to_duckdb_with_stats(
            table_name=table_name,
            df=combined,
            mode="overwrite",
            conn=conn,
        )
        loaded_tables.append(table_name)

    still_missing = [table for table in missing_before if not _table_exists_in_main(conn, table)]
    if any("missing_dependency_openpyxl" in err for err in read_errors):
        raise RuntimeError(
            "No se pudo autoload O2C desde raw_data porque falta openpyxl. "
            "Ejecuta: .venv_rf10_clean/bin/python -m pip install openpyxl"
        )
    status = "OK" if not still_missing else "PARTIAL"
    return {
        "status": status,
        "source_tables": source_tables,
        "target_tables": target_tables,
        "tables_loaded": loaded_tables,
        "tables_already_present": [t for t in target_tables if t not in missing_before],
        "tables_missing_after_load": still_missing,
        "nested_archives_count": len(nested_archives),
        "loaded_members_count": loaded_members_count,
        "invalid_nested_archives_count": len(invalid_nested_archives),
        "invalid_nested_archives_sample": invalid_nested_archives[:20],
        "read_errors_count": len(read_errors),
        "read_errors_sample": read_errors[:20],
    }


def _ensure_o2c_optional_placeholders(conn: Any) -> list[str]:
    placeholders: dict[str, list[str]] = {
        "VBPA": ["VBELN", "KUNNR"],
        "KNA1": ["KUNNR", "NAME1", "LAND1", "ORT01", "KTOKD", "KDGRP"],
        "KONV": ["KNUMV", "KWERT"],
        "LIKP": ["VBELN", "LFDAT", "WADAT_IST", "KUNNR"],
        "KNB1": ["KUNNR", "AKONT", "ZTERM", "MAHNA"],
        "BKPF": ["BUKRS", "BELNR", "GJAHR", "BUDAT"],
        "BSEG": [
            "BUKRS",
            "BELNR",
            "GJAHR",
            "KUNNR",
            "HKONT",
            "DMBTR",
            "WRBTR",
            "SHKZG",
            "ZFBDT",
            "AUGBL",
            "AUGDT",
            "ZTERM",
        ],
        "LIPS": ["VBELN", "POSNR", "VGBEL", "VGPOS", "LFIMG", "MATNR", "WERKS"],
    }
    created: list[str] = []
    for table_name, columns in placeholders.items():
        if _table_exists_in_main(conn, table_name):
            continue
        cols_sql = ", ".join(f'"{column}" VARCHAR' for column in columns)
        conn.execute(f'CREATE TABLE main."{table_name}" ({cols_sql})')
        created.append(table_name)
    return created


def _load_config_file(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"No existe fichero de config: {cfg_path}")
    text = cfg_path.read_text(encoding="utf-8")
    suffix = cfg_path.suffix.lower()
    if suffix in {".json"}:
        loaded = json.loads(text)
    elif suffix in {".yml", ".yaml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise RuntimeError("No se puede leer YAML sin PyYAML instalado") from exc
        loaded = yaml.safe_load(text)
    else:
        # fallback: intentar JSON primero y luego YAML
        try:
            loaded = json.loads(text)
        except Exception:
            try:
                import yaml  # type: ignore
            except Exception as exc:
                raise RuntimeError(
                    "Formato de --config no soportado (usa .json/.yml/.yaml)"
                ) from exc
            loaded = yaml.safe_load(text)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("--config debe contener un objeto raíz")
    return dict(loaded)


def _parse_select_tests(raw_value: Any) -> list[str] | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, list):
        values = [str(item).strip() for item in raw_value if str(item).strip()]
        return values or None
    raw = str(raw_value).strip()
    if not raw:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None


def _parse_select_values(raw_value: Any) -> list[str] | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, list):
        values = [str(item).strip() for item in raw_value if str(item).strip()]
        return values or None
    raw = str(raw_value).strip()
    if not raw:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None


def _normalize_llm_mode(raw_value: Any) -> str:
    mode = str(raw_value if raw_value is not None else "stub").strip().lower()
    if mode not in {"stub", "real"}:
        return "stub"
    return mode


def _normalize_process_family(raw_value: Any) -> str:
    value = str(raw_value if raw_value is not None else DEFAULT_PROCESS_FAMILY).strip().lower()
    if value not in {"p2p", "o2c"}:
        return DEFAULT_PROCESS_FAMILY
    return value


def _normalize_pipeline_mode(raw_value: Any) -> str:
    value = str(raw_value if raw_value is not None else "deterministic").strip().lower()
    if value not in {"deterministic", "graph"}:
        return "deterministic"
    return value


def _filter_catalog_test_ids(
    *,
    test_specs: list[dict[str, Any]],
    select_tests: list[str] | None = None,
    select_fraud_types: list[str] | None = None,
    select_tags: list[str] | None = None,
) -> list[str] | None:
    """Filtra tests por id/fraud_type/tags (RF13-05).

    Retorna:
    - `None`: ejecutar catálogo completo (sin filtros)
    - `list[str]`: subconjunto final en orden estable
    """
    specs_by_id: dict[str, dict[str, Any]] = {}
    catalog_order_ids: list[str] = []
    for spec in test_specs:
        if not isinstance(spec, dict):
            continue
        test_id = str(spec.get("id", "")).strip()
        if not test_id:
            continue
        if test_id in specs_by_id:
            continue
        specs_by_id[test_id] = spec
        catalog_order_ids.append(test_id)

    if select_tests is None and select_fraud_types is None and select_tags is None:
        return None

    if select_tests is not None:
        selected_ids = [test_id for test_id in select_tests if test_id in specs_by_id]
    else:
        selected_ids = list(catalog_order_ids)

    fraud_filter = {value.strip().lower() for value in (select_fraud_types or []) if value.strip()}
    tag_filter = {value.strip().lower() for value in (select_tags or []) if value.strip()}

    def _passes(spec: dict[str, Any]) -> bool:
        if fraud_filter:
            fraud_type = str(spec.get("fraud_type", "")).strip().lower()
            if fraud_type not in fraud_filter:
                return False
        if tag_filter:
            tags = spec.get("tags", [])
            tags_normalized: set[str] = set()
            if isinstance(tags, list):
                tags_normalized = {str(tag).strip().lower() for tag in tags if str(tag).strip()}
            if not (tags_normalized & tag_filter):
                return False
        return True

    return [test_id for test_id in selected_ids if _passes(specs_by_id[test_id])]


def _resolve_run_settings(args: argparse.Namespace) -> dict[str, Any]:
    cfg = _load_config_file(args.config)
    cloud_env = get_cloud_env_settings()

    def _pick(name: str, default: Any) -> Any:
        cli_value = getattr(args, name, None)
        if cli_value is not None:
            return cli_value
        if name in cfg and cfg[name] is not None:
            return cfg[name]
        return default

    resolved: dict[str, Any] = {
        "input_zip": str(_pick("input_zip", DEFAULT_RUN_INPUT_ZIP)),
        "run_id": _pick("run_id", None),
        "out_dir": str(_pick("out_dir", DEFAULT_OUT_DIR)),
        "db_path": str(_pick("db_path", DEFAULT_DB_PATH)),
        "schema_name": str(_pick("schema_name", DEFAULT_SCHEMA_NAME)),
        "table_name": str(_pick("table_name", DEFAULT_TABLE_NAME)),
        "catalog": str(_pick("catalog", DEFAULT_CATALOG_PATH)),
        "catalog_explicit": bool(getattr(args, "catalog", None) is not None or cfg.get("catalog") is not None),
        "weights_config": str(_pick("weights_config", DEFAULT_WEIGHTS_CONFIG)),
        "timeout_ms": _pick("timeout_ms", None),
        "sample_top_n": int(_pick("sample_top_n", DEFAULT_SAMPLE_TOP_N)),
        "top_k": _pick("top_k", None),
        "select_tests": _parse_select_tests(_pick("select_tests", None)),
        "select_fraud_types": _parse_select_values(_pick("select_fraud_types", None)),
        "select_tags": _parse_select_values(_pick("select_tags", None)),
        "kb_index_enabled": bool(_pick("kb_index_enabled", DEFAULT_KB_ENABLED)),
        "kb_index_explicit": bool(getattr(args, "kb_index_enabled", None) is not None or cfg.get("kb_index_enabled") is not None),
        "kb_index_cli_explicit": bool(getattr(args, "kb_index_enabled", None) is not None),
        "kb_sources_config": str(_pick("kb_sources_config", DEFAULT_KB_SOURCES_CONFIG)),
        "kb_chunking_config": str(_pick("kb_chunking_config", DEFAULT_KB_CHUNKING_CONFIG)),
        "kb_chroma_config": str(_pick("kb_chroma_config", DEFAULT_KB_CHROMA_CONFIG)),
        "llm_mode": _normalize_llm_mode(_pick("llm_mode", "stub")),
        "pipeline_mode": _normalize_pipeline_mode(_pick("pipeline_mode", "deterministic")),
        "process_family": _normalize_process_family(_pick("process_family", DEFAULT_PROCESS_FAMILY)),
        "process_family_explicit": bool(getattr(args, "process_family", None) is not None or cfg.get("process_family") is not None),
        "o2c_canonical_schema_config": str(
            _pick("o2c_canonical_schema_config", DEFAULT_O2C_CANONICAL_SCHEMA_CONFIG)
        ),
        "o2c_identity_config": str(_pick("o2c_identity_config", DEFAULT_O2C_IDENTITY_CONFIG)),
        "o2c_mapping_config": str(_pick("o2c_mapping_config", DEFAULT_O2C_MAPPING_CONFIG)),
        "o2c_target_schema": str(_pick("o2c_target_schema", DEFAULT_O2C_TARGET_SCHEMA)),
        "aws_region": cloud_env["aws_region"],
        "run_mode": cloud_env["run_mode"],
        "s3_input_uri": cloud_env["s3_input_uri"],
        "s3_output_uri": cloud_env["s3_output_uri"],
        "s3_state_uri": cloud_env["s3_state_uri"],
        "process_scope": cloud_env["process_scope"],
    }
    if resolved["timeout_ms"] is not None:
        resolved["timeout_ms"] = int(resolved["timeout_ms"])
    if resolved["top_k"] is not None:
        resolved["top_k"] = int(resolved["top_k"])
    return resolved


def _build_run_paths(run_dir: Path) -> dict[str, Path]:
    """Rutas canónicas del run para mantener estructura estable (RF10-03)."""
    return {
        "ingest_log": run_dir / "ingest_logs.jsonl",
        "run_metadata": run_dir / "run_metadata.json",
        "schema_summary": run_dir / "schema_summary.json",
        "data_validation_report": run_dir / "data_validation_report.json",
        "test_runner_log": run_dir / "test_runner_logs.jsonl",
        "test_runs": run_dir / "test_runs.json",
        "ranking_json": run_dir / "ranking.json",
        "ranking_parquet": run_dir / "ranking.parquet",
        "report_json": run_dir / "report.json",
        "report_md": run_dir / "report.md",
        "report_html": run_dir / "report.html",
        "tests_outputs_dir": run_dir / "tests_outputs",
        "drilldowns_dir": run_dir / "drilldowns",
        "run_structure": run_dir / "run_structure.json",
        "kb_index_manifest": run_dir / "kb_index_manifest.json",
        "kb_index_state": run_dir / "kb_index_state.json",
    }


def _build_test_report_cards(
    *,
    test_specs: list[dict[str, Any]],
    test_output_paths: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for spec in test_specs:
        test_id = str(spec.get("id", "")).strip()
        if not test_id:
            continue
        source = spec.get("source", {}) if isinstance(spec.get("source"), dict) else {}
        expected_output = (
            spec.get("expected_output", {}) if isinstance(spec.get("expected_output"), dict) else {}
        )
        card = {
            "test_id": test_id,
            "name": str(spec.get("name", "")),
            "fraud_type": str(spec.get("fraud_type", "")),
            "process_step": str(spec.get("process_step", "")),
            "description": str(spec.get("description", "")),
            "acfe_reference": str(source.get("reference", "")),
            "acfe_url": str(source.get("url", "")),
            "expected_output_notes": str(expected_output.get("notes", "")),
            "evidence_columns": list(spec.get("evidence_columns", []))
            if isinstance(spec.get("evidence_columns"), list)
            else [],
            "sample_artifact": str(test_output_paths.get(test_id, {}).get("sample_json", "")),
        }
        cards.append(card)
    return sorted(cards, key=lambda row: str(row.get("test_id", "")))


def _build_red_flags_activated(
    *,
    test_specs: list[dict[str, Any]],
    test_results: list[dict[str, Any]],
    test_output_paths: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Construye resumen de red flags activadas (RF13-17)."""
    specs_by_id: dict[str, dict[str, Any]] = {}
    for spec in test_specs:
        if not isinstance(spec, dict):
            continue
        test_id = str(spec.get("id", "")).strip()
        if test_id:
            specs_by_id[test_id] = spec

    activated: list[dict[str, Any]] = []
    for result in test_results:
        if not isinstance(result, dict):
            continue
        test_id = str(result.get("test_id", "")).strip()
        if not test_id:
            continue
        finding_count = int(result.get("finding_count", 0) or 0)
        if finding_count <= 0:
            continue
        spec = specs_by_id.get(test_id, {})
        source = spec.get("source", {}) if isinstance(spec.get("source"), dict) else {}
        activated.append(
            {
                "test_id": test_id,
                "red_flag_id": str(spec.get("red_flag_id", "")),
                "fraud_type": str(spec.get("fraud_type", "")),
                "acfe_reference": str(source.get("reference", "")),
                "finding_count": finding_count,
                "evidence_columns": list(spec.get("evidence_columns", []))
                if isinstance(spec.get("evidence_columns"), list)
                else [],
                "explanation": str(spec.get("description", "")),
                "sample_artifact": str(test_output_paths.get(test_id, {}).get("sample_json", "")),
            }
        )
    return sorted(activated, key=lambda row: str(row.get("test_id", "")))


def _write_run_structure_manifest(*, run_id: str, run_dir: Path, paths: dict[str, Path]) -> Path:
    payload = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "files": {
            key: str(value)
            for key, value in sorted(paths.items(), key=lambda item: item[0])
            if key not in {"tests_outputs_dir", "drilldowns_dir"}
        },
        "directories": {
            "tests_outputs_dir": str(paths["tests_outputs_dir"]),
            "drilldowns_dir": str(paths["drilldowns_dir"]),
        },
    }
    output = paths["run_structure"]
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def _ensure_report_dictionary_artifacts(*, run_dir: Path) -> tuple[Path, Path]:
    """Asegura artefactos mínimos de data dictionary dentro del run."""
    dd_json = run_dir / "data_dictionary.json"
    dd_md = run_dir / "data_dictionary.md"

    if not dd_json.exists():
        root_json = Path("data_dictionary.json")
        if root_json.exists():
            dd_json.write_bytes(root_json.read_bytes())
        else:
            dd_json.write_text("{}\n", encoding="utf-8")

    if not dd_md.exists():
        root_md = Path("data_dictionary.md")
        if root_md.exists():
            dd_md.write_bytes(root_md.read_bytes())
        else:
            dd_md.write_text("# Data Dictionary\n\nNo disponible para este run.\n", encoding="utf-8")

    return dd_json, dd_md


def _build_cloud_output_s3_uri(*, s3_output_uri: str, run_id: str) -> str:
    base = str(s3_output_uri).strip().rstrip("/")
    return f"{base}/{run_id}/"


def _resolve_cloud_input_zip_path(*, workspace_dir: Path, requested_input_zip: str) -> Path:
    requested = Path(str(requested_input_zip).strip())
    if requested.is_absolute() and requested.exists():
        return requested

    candidate = workspace_dir / requested
    if candidate.exists():
        return candidate

    basename = requested.name
    matches = sorted(workspace_dir.rglob(basename))
    if matches:
        return matches[0]

    zip_matches = sorted(workspace_dir.rglob("*.zip"))
    if zip_matches:
        return zip_matches[0]

    raise FileNotFoundError(
        f"No se encontró zip de entrada en workspace cloud. requested={requested_input_zip}"
    )


def _build_pipeline_args_for_workspace(
    *,
    settings: dict[str, Any],
    run_id: str,
    workspace_input_zip: Path,
    pipeline_mode: str = "deterministic",
) -> argparse.Namespace:
    return argparse.Namespace(
        input_zip=str(workspace_input_zip),
        run_id=run_id,
        out_dir="run_results",
        db_path="erp.duckdb",
        schema_name=settings["schema_name"],
        table_name=settings["table_name"],
        catalog=settings["catalog"],
        weights_config=settings["weights_config"],
        timeout_ms=settings["timeout_ms"],
        sample_top_n=settings["sample_top_n"],
        top_k=settings["top_k"],
        select_tests=settings["select_tests"],
        select_fraud_types=settings["select_fraud_types"],
        select_tags=settings["select_tags"],
        config=None,
        kb_index_enabled=settings["kb_index_enabled"],
        kb_sources_config=settings["kb_sources_config"],
        kb_chunking_config=settings["kb_chunking_config"],
        kb_chroma_config=settings["kb_chroma_config"],
        pipeline_mode=pipeline_mode,
        process_family=settings["process_family"],
        o2c_canonical_schema_config=settings["o2c_canonical_schema_config"],
        o2c_identity_config=settings["o2c_identity_config"],
        o2c_mapping_config=settings["o2c_mapping_config"],
        o2c_target_schema=settings["o2c_target_schema"],
        llm_mode=settings["llm_mode"],
    )


def _execute_local_pipeline_in_workspace(*, inner_args: argparse.Namespace, resolved_settings: dict[str, Any]) -> int:
    return _run_pipeline_local(inner_args, resolved_settings=resolved_settings)


def _execute_graph_pipeline_in_workspace(
    *,
    settings: dict[str, Any],
    run_id: str,
    workspace_input_zip: Path,
    process_scope: str,
    artifact_hash: str,
) -> int:
    run_dir = Path("run_results") / run_id
    schema_summary_path = (run_dir / "schema_summary.json").resolve()
    if not schema_summary_path.exists():
        raise FileNotFoundError(f"No existe schema_summary para ejecutar grafo: {schema_summary_path}")

    run_metadata_path = (run_dir / "run_metadata.json").resolve()
    dataset_hash = ""
    if run_metadata_path.exists():
        try:
            payload = json.loads(run_metadata_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                dataset_hash = str(payload.get("dataset_hash", "")).strip()
        except Exception:
            dataset_hash = ""

    schema_name = str(settings.get("schema_name", "")).strip()
    table_name = str(settings.get("table_name", "")).strip()
    process_family = str(settings.get("process_family", "")).strip().lower()
    if process_family == "o2c":
        if not schema_name or schema_name == DEFAULT_SCHEMA_NAME:
            schema_name = str(settings.get("o2c_target_schema", DEFAULT_O2C_TARGET_SCHEMA)).strip() or DEFAULT_O2C_TARGET_SCHEMA
        if not table_name or table_name == DEFAULT_TABLE_NAME:
            table_name = "o2c_order"

    def _abs_from_workspace(raw_value: str, default_value: str) -> str:
        value = str(raw_value).strip() or str(default_value).strip()
        if not value:
            return ""
        path = Path(value)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        return str(path)

    db_path_abs = _abs_from_workspace(str(settings.get("db_path", DEFAULT_DB_PATH)), DEFAULT_DB_PATH)
    catalog_path_abs = _abs_from_workspace(str(settings.get("catalog", DEFAULT_CATALOG_PATH)), DEFAULT_CATALOG_PATH)
    weights_config_abs = _abs_from_workspace(str(settings.get("weights_config", DEFAULT_WEIGHTS_CONFIG)), DEFAULT_WEIGHTS_CONFIG)
    kb_sources_abs = _abs_from_workspace(str(settings.get("kb_sources_config", "")), "")
    kb_chunking_abs = _abs_from_workspace(str(settings.get("kb_chunking_config", "")), "")
    kb_chroma_abs = _abs_from_workspace(str(settings.get("kb_chroma_config", "")), "")

    # Cloud graph:
    # - kb_index => rebuild/reindex (solo si se pide explícitamente por CLI)
    # - kb_search => uso de índice existente para contexto documental (activo por defecto)
    kb_index_rebuild_requested = (
        bool(settings.get("kb_index_enabled", False))
        if bool(settings.get("kb_index_cli_explicit", False))
        else False
    )
    kb_search_enabled_for_graph = True

    graph_state = run_graph_full(
        run_id=run_id,
        dataset_hash=dataset_hash,
        input_zip=str(workspace_input_zip),
        execute_kb_index=kb_index_rebuild_requested,
        run_metadata_overrides={
            "schema_summary_path": str(schema_summary_path),
            "catalog_path": catalog_path_abs,
            "persist_base_dir": "run_results",
            "weights_config": weights_config_abs,
            "llm_mode": str(settings.get("llm_mode", "stub")).strip(),
            "process_family": process_family,
            "process_scope": process_scope,
            "db_path": db_path_abs,
            "schema_name": schema_name,
            "table_name": table_name,
            "kb_index_enabled": kb_index_rebuild_requested,
            "kb_index_rebuild_requested": kb_index_rebuild_requested,
            "kb_search_enabled": kb_search_enabled_for_graph,
            "kb_sources_config": kb_sources_abs,
            "kb_chunking_config": kb_chunking_abs,
            "kb_chroma_config": kb_chroma_abs,
            "rf16_include_current_run": True,
            "rf16_auto_latest_p2p_o2c": True,
            "rf16_base_dir": "run_results",
            "artifact_hash": artifact_hash,
        },
    )

    graph_metadata = getattr(graph_state, "run_metadata", {})
    if not isinstance(graph_metadata, dict):
        graph_metadata = {}
    graph_status = str(graph_metadata.get("graph_status", "")).strip().upper()
    if graph_status == "ABORTED":
        reason = str(graph_metadata.get("graph_abort_reason", "")).strip() or "unknown"
        kb_abort_reason = reason.lower().startswith("node_failed:kb_index:")
        if kb_abort_reason and not kb_index_rebuild_requested:
            graph_metadata["graph_status"] = "OK_WITH_WARNINGS"
            graph_metadata["graph_warning"] = (
                "kb_index_failed_but_rebuild_not_requested"
            )
            graph_metadata["kb_index_status"] = "SKIPPED_NO_REBUILD"
            node_status = graph_metadata.setdefault("node_status", {})
            if isinstance(node_status, dict):
                node_status["kb_index"] = "SKIPPED"
            print(
                "[cloud] graph warning: kb_index abort ignorado "
                "(rebuild no solicitado explícitamente)"
            )
            graph_state_path = run_dir / "graph" / "graph_state.json"
            if graph_state_path.exists():
                try:
                    payload = json.loads(graph_state_path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        payload["run_metadata"] = graph_metadata
                        graph_state_path.write_text(
                            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8",
                        )
                except Exception:
                    pass
        else:
            raise RuntimeError(f"Grafo ABORTED: {reason}")

    required_graph_outputs = (
        run_dir / "graph" / "graph_state.json",
        run_dir / "graph" / "hypotheses.json",
        run_dir / "graph" / "selected_tests.json",
        run_dir / "graph" / "findings.json",
        run_dir / "graph" / "scores.json",
        run_dir / "graph" / "manifest.json",
    )
    missing = [str(path) for path in required_graph_outputs if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Grafo ejecutado sin artefactos mínimos ({len(missing)}): {', '.join(missing)}")
    return 0


def _build_cloud_artifacts_mappings_uri(*, s3_input_uri: str, scope: str) -> str:
    bucket, input_prefix = parse_s3_uri(s3_input_uri, allow_empty_prefix=True)
    normalized = input_prefix.strip("/")
    root_prefix = normalized
    if normalized.endswith("/inputs"):
        root_prefix = normalized[: -len("/inputs")]
    elif normalized == "inputs":
        root_prefix = ""
    mapping_prefix = f"artifacts/mappings/{scope}/"
    if root_prefix:
        return f"s3://{bucket}/{root_prefix.strip('/')}/{mapping_prefix}"
    return f"s3://{bucket}/{mapping_prefix}"


def _build_cloud_artifacts_category_uri(*, s3_input_uri: str, category: str, scope: str) -> str:
    bucket, input_prefix = parse_s3_uri(s3_input_uri, allow_empty_prefix=True)
    normalized = input_prefix.strip("/")
    root_prefix = normalized
    if normalized.endswith("/inputs"):
        root_prefix = normalized[: -len("/inputs")]
    elif normalized == "inputs":
        root_prefix = ""
    cat_prefix = f"artifacts/{category}/{scope}/"
    if root_prefix:
        return f"s3://{bucket}/{root_prefix.strip('/')}/{cat_prefix}"
    return f"s3://{bucket}/{cat_prefix}"


def _candidate_cloud_mapping_scopes(process_scope: str) -> list[str]:
    if process_scope == "both":
        return ["both", "p2p", "o2c", "shared"]
    return [process_scope, "shared"]


def _materialize_workspace_file_from_source_root(
    *,
    workspace_dir: Path,
    source_root: Path,
    relative_path: str,
    log_label: str,
) -> Path | None:
    rel = Path(str(relative_path).strip())
    if rel.is_absolute():
        return rel if rel.exists() else None
    target = workspace_dir / rel
    if target.exists():
        return target
    source = source_root / rel
    if not source.exists() or not source.is_file():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    print(f"[cloud] restored {log_label} (image fallback) -> {target}")
    return target


def _materialize_workspace_dir_from_source_root(
    *,
    workspace_dir: Path,
    source_root: Path,
    relative_path: str,
    log_label: str,
) -> Path | None:
    rel = Path(str(relative_path).strip())
    if rel.is_absolute():
        return rel if rel.exists() else None
    target = workspace_dir / rel
    if target.exists() and any(target.rglob("*")):
        return target
    source = source_root / rel
    if not source.exists() or not source.is_dir():
        return None
    target.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        out = target / path.relative_to(source)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(path.read_bytes())
    print(f"[cloud] restored {log_label} (image fallback) -> {target}")
    return target


def _materialize_workspace_glob_from_source_root(
    *,
    workspace_dir: Path,
    source_root: Path,
    glob_pattern: str,
    log_label: str,
) -> int:
    pattern = str(glob_pattern).strip()
    if not pattern:
        return 0
    restored_count = 0
    for source in sorted(source_root.glob(pattern)):
        if not source.is_file():
            continue
        rel = source.relative_to(source_root)
        target = workspace_dir / rel
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        restored_count += 1
    if restored_count > 0:
        print(f"[cloud] restored {log_label} (image fallback) -> {restored_count} files")
    return restored_count


def _materialize_cloud_kb_sources_from_source_root(
    *,
    workspace_dir: Path,
    source_root: Path,
    kb_sources_config_path: str,
) -> int:
    cfg_path = str(kb_sources_config_path).strip()
    if not cfg_path:
        return 0
    config_payload = load_kb_sources_config(cfg_path)
    sources = config_payload.get("sources", [])
    if not isinstance(sources, list):
        return 0

    restored_total = 0
    for source in sources:
        if not isinstance(source, dict):
            continue
        if not bool(source.get("enabled", True)):
            continue
        source_id = str(source.get("source_id", "")).strip() or "kb_source"
        source_type = str(source.get("type", "")).strip()
        source_path = str(source.get("path", "")).strip()
        if source_type == "file":
            restored = _materialize_workspace_file_from_source_root(
                workspace_dir=workspace_dir,
                source_root=source_root,
                relative_path=source_path,
                log_label=f"kb_source:{source_id}",
            )
            if restored is not None:
                restored_total += 1
        elif source_type == "glob":
            restored_total += _materialize_workspace_glob_from_source_root(
                workspace_dir=workspace_dir,
                source_root=source_root,
                glob_pattern=source_path,
                log_label=f"kb_source:{source_id}",
            )
    return restored_total


def _restore_cloud_catalog_dir(
    *,
    workspace_dir: Path,
    settings: dict[str, Any],
    process_family: str,
    target_relative_path: str,
) -> Path | None:
    target = workspace_dir / target_relative_path
    scopes = [process_family, "shared"]
    for scope in scopes:
        uri = _build_cloud_artifacts_category_uri(
            s3_input_uri=str(settings["s3_input_uri"]),
            category="catalogs",
            scope=scope,
        )
        staging_dir = workspace_dir / ".cloud_restore" / "catalogs" / scope
        result = download_s3_prefix_to_local_dir(s3_uri=uri, local_dir=staging_dir)
        if int(result.get("downloaded_count", 0) or 0) <= 0:
            continue
        target.mkdir(parents=True, exist_ok=True)
        for file_path in staging_dir.rglob("*"):
            if not file_path.is_file():
                continue
            out = target / file_path.relative_to(staging_dir)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(file_path.read_bytes())
        print(f"[cloud] restored catalog ({scope}) -> {target}")
    if target.exists() and any(path.is_file() for path in target.rglob("*")):
        return target
    return None


def _restore_cloud_config_file_from_mappings(
    *,
    workspace_dir: Path,
    settings: dict[str, Any],
    process_scope: str,
    source_filename: str,
    target_relative_path: Path,
    log_label: str,
) -> Path | None:
    target_path = workspace_dir / target_relative_path
    for scope in _candidate_cloud_mapping_scopes(process_scope):
        mapping_uri = _build_cloud_artifacts_mappings_uri(
            s3_input_uri=str(settings["s3_input_uri"]),
            scope=scope,
        )
        staging_dir = workspace_dir / ".cloud_restore" / "mappings" / scope
        result = download_s3_prefix_to_local_dir(
            s3_uri=mapping_uri,
            local_dir=staging_dir,
        )
        source_path = staging_dir / source_filename
        if int(result.get("downloaded_count", 0) or 0) <= 0 or not source_path.exists():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(source_path.read_bytes())
        print(f"[cloud] restored {log_label} -> {target_path}")
        return target_path
    return None


def _restore_cloud_red_flags_mapping(
    *,
    workspace_dir: Path,
    settings: dict[str, Any],
    process_scope: str,
) -> Path | None:
    return _restore_cloud_config_file_from_mappings(
        workspace_dir=workspace_dir,
        settings=settings,
        process_scope=process_scope,
        source_filename="red_flags_mapping.yaml",
        target_relative_path=Path("config/red_flags_mapping.yaml"),
        log_label="red_flags_mapping",
    )


def _restore_cloud_weights_config(
    *,
    workspace_dir: Path,
    settings: dict[str, Any],
    process_scope: str,
) -> Path | None:
    return _restore_cloud_config_file_from_mappings(
        workspace_dir=workspace_dir,
        settings=settings,
        process_scope=process_scope,
        source_filename="weights.yaml",
        target_relative_path=Path("config/weights.yaml"),
        log_label="weights",
    )


def _run_pipeline_cloud(args: argparse.Namespace, settings: dict[str, Any]) -> int:
    run_id = str(settings["run_id"]).strip() if settings["run_id"] else _default_run_id()
    process_scope = validate_process_scope(settings["process_scope"])
    pipeline_mode = str(settings.get("pipeline_mode", "deterministic")).strip().lower() or "deterministic"
    process_family = str(settings.get("process_family", DEFAULT_PROCESS_FAMILY)).strip().lower() or DEFAULT_PROCESS_FAMILY
    explicit_process_family = bool(settings.get("process_family_explicit", False))
    if process_scope in {"o2c", "both"} and not explicit_process_family:
        print(
            "ERROR: en RUN_MODE=cloud con PROCESS_SCOPE=o2c|both debes indicar --process-family explícito (p2p|o2c)",
            file=sys.stderr,
        )
        return 2
    print(f"[cloud] RUN_MODE=cloud | run_id={run_id} | process_scope={process_scope}")

    tmp_dir_obj: tempfile.TemporaryDirectory[str] | None = None
    previous_cwd = Path.cwd()
    previous_run_mode = os.getenv("RUN_MODE")
    try:
        tmp_dir_obj = tempfile.TemporaryDirectory(prefix="erp_fraud_cloud_")
        workspace_dir = Path(tmp_dir_obj.name)
        source_root = previous_cwd
        print(f"[cloud] workspace={workspace_dir}")

        download_required_inputs(
            local_input_dir=workspace_dir,
            s3_input_uri=settings["s3_input_uri"],
        )
        # Restore catálogo esperado por process_family en workspace (S3 first, image fallback).
        requested_catalog = str(settings.get("catalog", DEFAULT_CATALOG_PATH)).strip() or DEFAULT_CATALOG_PATH
        if process_family == "o2c" and not bool(settings.get("catalog_explicit", False)):
            requested_catalog = "tests/catalog_o2c"
            settings["catalog"] = requested_catalog
        restored_catalog = _restore_cloud_catalog_dir(
            workspace_dir=workspace_dir,
            settings=settings,
            process_family=process_family,
            target_relative_path=requested_catalog,
        )
        if restored_catalog is None:
            restored_catalog = _materialize_workspace_dir_from_source_root(
                workspace_dir=workspace_dir,
                source_root=source_root,
                relative_path=requested_catalog,
                log_label="catalog",
            )
        if restored_catalog is not None:
            settings["catalog"] = str(restored_catalog)

        # Materialize config files required by deterministic+graph flows.
        for cfg_key in (
            "weights_config",
            "o2c_canonical_schema_config",
            "o2c_identity_config",
            "o2c_mapping_config",
            "kb_sources_config",
            "kb_chunking_config",
            "kb_chroma_config",
        ):
            restored = _materialize_workspace_file_from_source_root(
                workspace_dir=workspace_dir,
                source_root=source_root,
                relative_path=str(settings.get(cfg_key, "")).strip(),
                log_label=cfg_key,
            )
            if restored is not None:
                settings[cfg_key] = str(restored)
        red_flags_path = _restore_cloud_red_flags_mapping(
            workspace_dir=workspace_dir,
            settings=settings,
            process_scope=process_scope,
        )
        if red_flags_path is None:
            _materialize_workspace_file_from_source_root(
                workspace_dir=workspace_dir,
                source_root=source_root,
                relative_path="config/red_flags_mapping.yaml",
                log_label="red_flags_mapping",
            )
        weights_path = _restore_cloud_weights_config(
            workspace_dir=workspace_dir,
            settings=settings,
            process_scope=process_scope,
        )
        if weights_path is None:
            _materialize_workspace_file_from_source_root(
                workspace_dir=workspace_dir,
                source_root=source_root,
                relative_path="config/weights.yaml",
                log_label="weights",
            )
        if bool(settings.get("kb_index_enabled", False)):
            _materialize_cloud_kb_sources_from_source_root(
                workspace_dir=workspace_dir,
                source_root=source_root,
                kb_sources_config_path=str(settings.get("kb_sources_config", "")).strip(),
            )

        workspace_input_zip = _resolve_cloud_input_zip_path(
            workspace_dir=workspace_dir,
            requested_input_zip=settings["input_zip"],
        )

        artifact_payload = compute_artifact_hash(
            project_root=workspace_dir,
            process_scope=process_scope,
        )
        artifact_hash = str(artifact_payload.get("artifact_hash", "")).strip()
        previous_state = read_last_artifact_hash_state(
            process_scope=process_scope,
            s3_state_uri=settings["s3_state_uri"],
        )
        print(
            "[cloud] artifact_hash="
            f"{artifact_hash[:12]}... | previous_state={'yes' if previous_state else 'no'}"
        )

        inner_args = _build_pipeline_args_for_workspace(
            settings=settings,
            run_id=run_id,
            workspace_input_zip=workspace_input_zip,
            pipeline_mode="deterministic",
        )
        os.chdir(workspace_dir)
        os.environ["RUN_MODE"] = "local"
        inner_settings = _resolve_run_settings(inner_args)
        inner_settings["process_scope"] = process_scope
        inner_settings["artifact_hash_override"] = artifact_hash

        exit_code = _execute_local_pipeline_in_workspace(
            inner_args=inner_args,
            resolved_settings=inner_settings,
        )
        if exit_code != 0:
            print("[cloud] pipeline local en workspace falló; no se actualiza state store")
            return int(exit_code)

        if pipeline_mode == "graph":
            if process_scope == "both":
                print(
                    "ERROR: pipeline_mode=graph no soporta PROCESS_SCOPE=both en un único run. "
                    "Lanza dos runs (p2p y o2c) con --process-family explícito.",
                    file=sys.stderr,
                )
                return 2
            if process_family not in {"p2p", "o2c"}:
                print(f"ERROR: process_family inválido para graph: {process_family}", file=sys.stderr)
                return 2
            graph_code = _execute_graph_pipeline_in_workspace(
                settings=inner_settings,
                run_id=run_id,
                workspace_input_zip=workspace_input_zip,
                process_scope=process_scope,
                artifact_hash=artifact_hash,
            )
            if graph_code != 0:
                print("[cloud] ejecución del grafo falló; no se actualiza state store", file=sys.stderr)
                return int(graph_code)

        local_run_dir = workspace_dir / "run_results" / run_id
        output_uri = _build_cloud_output_s3_uri(s3_output_uri=settings["s3_output_uri"], run_id=run_id)
        upload_run_outputs(local_run_dir=local_run_dir, s3_output_uri=output_uri)

        write_last_artifact_hash_state(
            last_artifact_hash=artifact_hash,
            last_run_id=run_id,
            process_scope=process_scope,
            s3_state_uri=settings["s3_state_uri"],
        )
        print(f"[cloud] run completado y estado actualizado | run_id={run_id}")
        return 0
    except Exception as exc:
        print(f"ERROR: cloud runner falló: {exc}", file=sys.stderr)
        return 1
    finally:
        os.chdir(previous_cwd)
        if previous_run_mode is None:
            os.environ.pop("RUN_MODE", None)
        else:
            os.environ["RUN_MODE"] = previous_run_mode
        if tmp_dir_obj is not None:
            tmp_dir_obj.cleanup()


def _run_pipeline(args: argparse.Namespace) -> int:
    settings = _resolve_run_settings(args)
    if str(settings.get("run_mode", "local")).strip().lower() == "cloud":
        return _run_pipeline_cloud(args, settings)
    return _run_pipeline_local(args, resolved_settings=settings)


def _run_pipeline_local(args: argparse.Namespace, *, resolved_settings: dict[str, Any] | None = None) -> int:
    settings = resolved_settings or _resolve_run_settings(args)
    run_id = str(settings["run_id"]).strip() if settings["run_id"] else _default_run_id()
    run_dir = Path(settings["out_dir"]) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_paths = _build_run_paths(run_dir)
    run_paths["tests_outputs_dir"].mkdir(parents=True, exist_ok=True)
    run_paths["drilldowns_dir"].mkdir(parents=True, exist_ok=True)
    logger = IngestJsonLogger(run_id=run_id, log_path=run_paths["ingest_log"])

    try:
        logger.log_ingest_start(
            input_zip=settings["input_zip"],
            db_path=settings["db_path"],
            catalog_path=settings["catalog"],
            out_dir=settings["out_dir"],
            llm_mode=settings["llm_mode"],
            process_family=settings["process_family"],
        )
        artifact_hash_override = str(settings.get("artifact_hash_override", "")).strip()
        if artifact_hash_override:
            artifact_payload = {"artifact_hash": artifact_hash_override, "process_scope": settings["process_scope"]}
            artifact_hash = artifact_hash_override
        else:
            artifact_payload = compute_artifact_hash(
                project_root=".",
                process_scope=settings["process_scope"],
            )
            artifact_hash = str(artifact_payload.get("artifact_hash", "")).strip()
        if settings["process_family"] == "o2c":
            raw = Path(settings["input_zip"]).read_bytes()
            dataset_hash = hashlib.sha256(raw).hexdigest()
        else:
            dataset_hash_result = calcular_dataset_hash(settings["input_zip"])
            dataset_hash = dataset_hash_result.dataset_hash

        if settings["process_family"] == "o2c":
            conn = get_duckdb_connection(settings["db_path"])
            try:
                raw_autoload_summary = _load_o2c_raw_tables_from_zip_if_needed(
                    conn=conn,
                    zip_path=settings["input_zip"],
                    canonical_schema_config_path=settings["o2c_canonical_schema_config"],
                )
                created_placeholders = _ensure_o2c_optional_placeholders(conn)
                transform_payload = transform_raw_to_o2c_canonical(
                    conn=conn,
                    canonical_schema_config_path=settings["o2c_canonical_schema_config"],
                    identity_config_path=settings["o2c_identity_config"],
                    mapping_config_path=settings["o2c_mapping_config"],
                    target_schema=settings["o2c_target_schema"],
                )
                data_validation_report_path = write_o2c_validation_report_json(
                    run_paths["data_validation_report"],
                    conn=conn,
                    canonical_schema_config_path=settings["o2c_canonical_schema_config"],
                    target_schema=settings["o2c_target_schema"],
                )
                validation_payload = json.loads(data_validation_report_path.read_text(encoding="utf-8"))
                validation_summary = (
                    validation_payload.get("summary", {}) if isinstance(validation_payload, dict) else {}
                )
                validation_status = str(validation_summary.get("overall_status", "ERROR")).strip().upper() or "ERROR"
                overall_status = "OK" if validation_status == "OK" else "ERROR"

                schema_summary_path = write_schema_summary_json(
                    run_paths["schema_summary"],
                    db_path=settings["db_path"],
                    schema_name=settings["o2c_target_schema"],
                )
            finally:
                conn.close()

            run_metadata_path = write_run_metadata_json(
                run_paths["run_metadata"],
                run_id=run_id,
                dataset_hash=dataset_hash,
                project_root=".",
                process_family=settings["process_family"],
                process_scope=settings["process_scope"],
                artifact_hash=artifact_hash,
            )
            try:
                run_metadata_payload = json.loads(run_metadata_path.read_text(encoding="utf-8"))
                if isinstance(run_metadata_payload, dict):
                    run_metadata_payload["llm_mode"] = settings["llm_mode"]
                    run_metadata_payload["process_family"] = settings["process_family"]
                    run_metadata_payload["process_scope"] = settings["process_scope"]
                    run_metadata_payload["artifact_hash"] = artifact_hash
                    run_metadata_payload["artifact_files_count"] = int(artifact_payload.get("file_count", 0) or 0)
                    run_metadata_payload["o2c_target_schema"] = settings["o2c_target_schema"]
                    run_metadata_payload["o2c_transform_status"] = transform_payload
                    run_metadata_payload["o2c_raw_autoload"] = raw_autoload_summary
                    run_metadata_payload["o2c_optional_placeholders_created"] = created_placeholders
                    run_metadata_payload["o2c_validation_summary"] = validation_summary
                    run_metadata_path.write_text(
                        json.dumps(run_metadata_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
            except Exception:
                pass

            test_specs = load_test_specs_from_catalog(settings["catalog"], validate_schema=True)
            test_runner = TestRunner(
                db_path=settings["db_path"],
                schema_name=settings["o2c_target_schema"],
                table_name="o2c_order",
            )
            if validation_status != "OK":
                results = []
                logger.log_warning(
                    "Run O2C bloqueado por validación técnica crítica",
                    validation_report=data_validation_report_path,
                    validation_status=validation_status,
                )
            else:
                selected_ids = _filter_catalog_test_ids(
                    test_specs=test_specs,
                    select_tests=settings["select_tests"],
                    select_fraud_types=settings["select_fraud_types"],
                    select_tags=settings["select_tags"],
                )
                if selected_ids is not None:
                    results = test_runner.run_all(
                        selected_ids,
                        catalog_path=settings["catalog"],
                        validate_schema=True,
                        timeout_ms=settings["timeout_ms"],
                        run_id=run_id,
                        log_path=run_paths["test_runner_log"],
                    )
                else:
                    results = test_runner.run_all_from_catalog(
                        catalog_path=settings["catalog"],
                        validate_schema=True,
                        timeout_ms=settings["timeout_ms"],
                        run_id=run_id,
                        log_path=run_paths["test_runner_log"],
                    )

            test_runs_payload = test_runner.build_test_runs_payload(results=results, run_id=run_id)
            test_runs_path = test_runner.write_test_runs_json(
                output_path=run_paths["test_runs"],
                run_id=run_id,
                results=results,
            )
            test_runs = list(test_runs_payload.get("test_runs", []))
            test_output_paths = write_test_results_by_test_id(
                run_dir=run_dir,
                test_results=results,
                formats=("jsonl", "parquet"),
                sample_top_n=settings["sample_top_n"],
            )
            specs_by_id = {
                str(spec.get("id", "")).strip(): spec
                for spec in test_specs
                if isinstance(spec, dict) and str(spec.get("id", "")).strip()
            }
            executed_specs = [
                specs_by_id[test_id]
                for test_id in sorted(test_output_paths.keys())
                if test_id in specs_by_id
            ]
            test_report_cards = _build_test_report_cards(
                test_specs=executed_specs,
                test_output_paths=test_output_paths,
            )
            red_flags_activated = _build_red_flags_activated(
                test_specs=executed_specs,
                test_results=results,
                test_output_paths=test_output_paths,
            )
            weights_cfg = load_weights_config(settings["weights_config"])
            if settings["top_k"] is not None:
                top_k = int(settings["top_k"])
            else:
                top_k = resolve_ranking_top_k(weights_config=weights_cfg, default_top_k=20)
            ranking_rows = aggregate_findings_by_entity(
                test_results=results,
                weights_config=weights_cfg,
            )
            ranking_paths = write_ranking_outputs(
                run_dir=run_dir,
                ranking_rows=ranking_rows,
                formats=("json", "parquet"),
                top_k=top_k,
            )
            tests_ok = sum(1 for row in test_runs if str(row.get("status", "")).upper() == "OK")
            tests_error = sum(1 for row in test_runs if str(row.get("status", "")).upper() == "ERROR")
            tests_timeout = sum(1 for row in test_runs if str(row.get("status", "")).upper() == "TIMEOUT")
            findings_total = sum(int(item.get("finding_count", 0) or 0) for item in results)
            overall_status = "ERROR" if (validation_status != "OK" or tests_error > 0) else "OK"

            extra_artifacts: dict[str, str] = {
                "run_metadata_json": str(run_metadata_path),
                "schema_summary_json": str(schema_summary_path),
                "schema_summary_json_run": str(schema_summary_path),
                "o2c_validation_report_json": str(data_validation_report_path),
                "test_runs_json": str(test_runs_path),
            }
            dd_json_path, dd_md_path = _ensure_report_dictionary_artifacts(run_dir=run_dir)
            extra_artifacts["data_dictionary_json"] = str(dd_json_path)
            extra_artifacts["data_dictionary_md"] = str(dd_md_path)
            for key, path in ranking_paths.items():
                extra_artifacts[f"ranking_{key}"] = str(path)
            for test_id, paths in test_output_paths.items():
                for kind, path in paths.items():
                    extra_artifacts[f"tests_outputs.{test_id}.{kind}"] = str(path)

            report_payload = build_report_json_payload(
                run_id=run_id,
                dataset_hash=dataset_hash,
                out_dir=settings["out_dir"],
                summary={
                    "overall_status": overall_status,
                    "tests_total": len(test_runs),
                    "tests_ok": tests_ok,
                    "tests_error": tests_error,
                    "tests_timeout": tests_timeout,
                    "findings_total": findings_total,
                    "ranking_entities": len(ranking_rows),
                },
                ranking=ranking_rows[:top_k],
                top_k=top_k,
                test_runs=test_runs,
                artifact_paths=extra_artifacts,
                errors=[],
                metadata_extra={
                    "input_zip": settings["input_zip"],
                    "out_dir": settings["out_dir"],
                    "llm_mode": settings["llm_mode"],
                    "process_family": settings["process_family"],
                    "o2c_target_schema": settings["o2c_target_schema"],
                    "o2c_canonical_schema_config": settings["o2c_canonical_schema_config"],
                    "o2c_identity_config": settings["o2c_identity_config"],
                    "o2c_mapping_config": settings["o2c_mapping_config"],
                    "o2c_transform_status": transform_payload,
                    "o2c_raw_autoload": raw_autoload_summary,
                    "o2c_optional_placeholders_created": created_placeholders,
                    "o2c_validation_summary": validation_summary,
                    "test_report_cards": test_report_cards,
                    "red_flags_activated": red_flags_activated,
                },
            )
            report_json_path = write_report_json(
                output_path=run_paths["report_json"],
                payload=report_payload,
            )
            report_md_path = write_report_markdown_from_report_json(
                report_json_path=report_json_path,
                report_md_path=run_paths["report_md"],
            )
            render_report_markdown_to_html(
                report_md_path=report_md_path,
                report_html_path=run_paths["report_html"],
            )
            write_or_update_report_markdown_with_data_validation(
                report_md_path=report_md_path,
                data_validation_report_path=data_validation_report_path,
            )
            write_or_update_report_markdown_with_drilldown_instructions(
                report_md_path=report_md_path,
                run_id=run_id,
            )
            _write_run_structure_manifest(run_id=run_id, run_dir=run_dir, paths=run_paths)
            missing_links = validate_report_artifact_paths_exist(
                report_payload=report_payload,
                base_path=".",
            )
            if missing_links:
                logger.log_warning(
                    "Reporte O2C con enlaces de artefactos faltantes",
                    missing_artifacts=missing_links,
                )
                print(
                    f"ERROR: report.json contiene {len(missing_links)} artifact_paths inexistentes",
                    file=sys.stderr,
                )
                return 1
            try:
                validate_required_run_outputs(run_dir=run_dir)
            except RunOutputValidationError as exc:
                logger.log_error("Validación de outputs obligatorios falló", error=str(exc))
                print(f"ERROR: outputs obligatorios incompletos: {exc}", file=sys.stderr)
                return 1

            if str(settings.get("pipeline_mode", "deterministic")).strip().lower() == "graph":
                graph_code = _execute_graph_pipeline_in_workspace(
                    settings=settings,
                    run_id=run_id,
                    workspace_input_zip=Path(settings["input_zip"]),
                    process_scope=str(settings.get("process_scope", "p2p")).strip(),
                    artifact_hash=artifact_hash,
                )
                if graph_code != 0:
                    logger.log_error("Ejecución grafo falló tras pipeline base", error=str(graph_code))
                    return int(graph_code)

            logger.log_ingest_end(
                status=overall_status,
                tables_loaded=int(transform_payload.get("entities_ok", 0)),
                tests_total=len(test_runs),
                findings_total=findings_total,
                run_dir=str(run_dir),
                process_family=settings["process_family"],
            )
            print(
                "OK: run completado "
                f"(run_id={run_id}, process_family=o2c, tests={len(test_runs)}, findings={findings_total}, status={overall_status}, out={run_dir})"
            )
            return 0 if overall_status == "OK" else 1

        validar_ficheros_esperados_joint_datasets(settings["input_zip"])
        files = listar_ficheros_joint_datasets(settings["input_zip"])

        table_stats: list[dict[str, object]] = []
        loaded_tables: list[str] = []

        for file_name in files:
            suffix = Path(file_name).suffix.lower()
            if suffix not in {".csv", ".parquet"}:
                continue

            table_name = _safe_table_name_from_file(file_name)
            df = cargar_fichero_tabular_desde_zip(settings["input_zip"], file_name)
            df, type_summary = normalizar_tipos_dataframe(df, fail_on_parse_errors=False)
            df, clean_summary = limpiar_tecnicamente_dataframe(df)

            stats = load_table_to_duckdb_with_stats(
                table_name=table_name,
                df=df,
                mode="overwrite",
                db_path=settings["db_path"],
            )
            loaded_tables.append(table_name)
            table_stats.append(
                {
                    "table_name": table_name,
                    "source_file": file_name,
                    "rows_loaded": stats.rows_loaded,
                    "duration_ms": stats.duration_ms,
                    "type_normalization": {
                        "date_columns": list(type_summary.date_columns),
                        "amount_columns": list(type_summary.amount_columns),
                        "id_columns": list(type_summary.id_columns),
                    },
                    "technical_cleaning": {
                        "columns_processed": list(clean_summary.columns_processed),
                        "trimmed_cells": clean_summary.trimmed_cells,
                        "nulls_normalized": clean_summary.nulls_normalized,
                    },
                }
            )
            logger.log_table_load(
                table_name=table_name,
                source_file=file_name,
                rows_loaded=stats.rows_loaded,
                duration_ms=stats.duration_ms,
            )

        schema_summary_path = write_schema_summary_json(
            run_paths["schema_summary"],
            db_path=settings["db_path"],
            schema_name=settings["schema_name"],
        )
        run_metadata_path = write_run_metadata_json(
            run_paths["run_metadata"],
            run_id=run_id,
            dataset_hash=dataset_hash,
            project_root=".",
            process_family=settings["process_family"],
            process_scope=settings["process_scope"],
            artifact_hash=artifact_hash,
        )
        try:
            run_metadata_payload = json.loads(run_metadata_path.read_text(encoding="utf-8"))
            if isinstance(run_metadata_payload, dict):
                run_metadata_payload["llm_mode"] = settings["llm_mode"]
                run_metadata_payload["process_family"] = settings["process_family"]
                run_metadata_payload["process_scope"] = settings["process_scope"]
                run_metadata_payload["artifact_hash"] = artifact_hash
                run_metadata_payload["artifact_files_count"] = int(artifact_payload.get("file_count", 0) or 0)
                run_metadata_path.write_text(
                    json.dumps(run_metadata_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        except Exception:
            pass

        test_specs = load_test_specs_from_catalog(settings["catalog"], validate_schema=True)
        schema_summary_payload = json.loads(schema_summary_path.read_text(encoding="utf-8"))
        validate_catalog_against_schema_summary(
            test_specs=test_specs,
            schema_summary_payload=schema_summary_payload,
        )
        validation_outcome = run_technical_validation_before_tests(
            test_specs=test_specs,
            report_output_path=run_paths["data_validation_report"],
            db_path=settings["db_path"],
            schema_name=settings["schema_name"],
        )

        kb_index_status: str = "DISABLED"
        kb_index_error: str | None = None
        kb_manifest_path: Path | None = None
        if settings["kb_index_enabled"]:
            try:
                kb_manifest = build_kb_index(
                    kb_sources_config_path=settings["kb_sources_config"],
                    kb_chunking_config_path=settings["kb_chunking_config"],
                    kb_chroma_config_path=settings["kb_chroma_config"],
                    base_dir=".",
                    output_manifest_path=run_paths["kb_index_manifest"],
                    index_state_path=run_paths["kb_index_state"],
                    incremental_rebuild=True,
                )
                kb_index_status = "OK"
                kb_manifest_path = run_paths["kb_index_manifest"]
                logger.log_event(
                    level="INFO",
                    event="kb_index_rebuild",
                    kb_chunks_indexed=kb_manifest.get("chunks_indexed", 0),
                    kb_sources_used=len(kb_manifest.get("sources_used", [])),
                    kb_sources_skipped=len(kb_manifest.get("sources_skipped", [])),
                )
            except Exception as kb_exc:
                kb_index_status = "ERROR"
                kb_index_error = str(kb_exc)
                logger.log_warning(
                    "KB index rebuild falló; se continúa sin bloquear pipeline",
                    error=kb_index_error,
                )

        test_runner = TestRunner(
            db_path=settings["db_path"],
            schema_name=settings["schema_name"],
            table_name=settings["table_name"],
        )

        if validation_outcome.should_block_run:
            results: list[dict] = []
            logger.log_warning(
                "Run bloqueado por validación técnica crítica",
                critical_errors_count=validation_outcome.critical_errors_count,
                validation_report=validation_outcome.report_path,
            )
        else:
            selected_ids = _filter_catalog_test_ids(
                test_specs=test_specs,
                select_tests=settings["select_tests"],
                select_fraud_types=settings["select_fraud_types"],
                select_tags=settings["select_tags"],
            )
            if selected_ids is not None:
                results = test_runner.run_all(
                    selected_ids,
                    catalog_path=settings["catalog"],
                    validate_schema=True,
                    timeout_ms=settings["timeout_ms"],
                    run_id=run_id,
                    log_path=run_paths["test_runner_log"],
                )
            else:
                results = test_runner.run_all_from_catalog(
                    catalog_path=settings["catalog"],
                    validate_schema=True,
                    timeout_ms=settings["timeout_ms"],
                    run_id=run_id,
                    log_path=run_paths["test_runner_log"],
                )

        test_runs_payload = test_runner.build_test_runs_payload(results=results, run_id=run_id)
        test_runs_path = test_runner.write_test_runs_json(
            output_path=run_paths["test_runs"],
            run_id=run_id,
            results=results,
        )
        test_runs = list(test_runs_payload.get("test_runs", []))

        test_output_paths = write_test_results_by_test_id(
            run_dir=run_dir,
            test_results=results,
            formats=("jsonl", "parquet"),
            sample_top_n=settings["sample_top_n"],
        )
        specs_by_id = {
            str(spec.get("id", "")).strip(): spec
            for spec in test_specs
            if isinstance(spec, dict) and str(spec.get("id", "")).strip()
        }
        executed_specs = [
            specs_by_id[test_id]
            for test_id in sorted(test_output_paths.keys())
            if test_id in specs_by_id
        ]
        test_report_cards = _build_test_report_cards(
            test_specs=executed_specs,
            test_output_paths=test_output_paths,
        )
        red_flags_activated = _build_red_flags_activated(
            test_specs=executed_specs,
            test_results=results,
            test_output_paths=test_output_paths,
        )

        weights_cfg = load_weights_config(settings["weights_config"])
        if settings["top_k"] is not None:
            top_k = int(settings["top_k"])
        else:
            top_k = resolve_ranking_top_k(weights_config=weights_cfg, default_top_k=20)
        ranking_rows = aggregate_findings_by_entity(
            test_results=results,
            weights_config=weights_cfg,
        )
        ranking_paths = write_ranking_outputs(
            run_dir=run_dir,
            ranking_rows=ranking_rows,
            formats=("json", "parquet"),
            top_k=top_k,
        )
        ranking_paths["json"] = str(run_paths["ranking_json"])
        ranking_paths["parquet"] = str(run_paths["ranking_parquet"])

        tests_ok = sum(1 for row in test_runs if str(row.get("status", "")).upper() == "OK")
        tests_error = sum(1 for row in test_runs if str(row.get("status", "")).upper() == "ERROR")
        tests_timeout = sum(1 for row in test_runs if str(row.get("status", "")).upper() == "TIMEOUT")
        findings_total = sum(int(item.get("finding_count", 0) or 0) for item in results)
        overall_status = "ERROR" if (validation_outcome.should_block_run or tests_error > 0) else "OK"

        extra_artifacts: dict[str, str] = {
            "run_metadata_json": str(run_metadata_path),
            "schema_summary_json": str(schema_summary_path),
            "schema_summary_json_run": str(schema_summary_path),
            "data_validation_report_json": str(validation_outcome.report_path),
            "test_runs_json": str(test_runs_path),
        }
        dd_json_path, dd_md_path = _ensure_report_dictionary_artifacts(run_dir=run_dir)
        extra_artifacts["data_dictionary_json"] = str(dd_json_path)
        extra_artifacts["data_dictionary_md"] = str(dd_md_path)
        if kb_manifest_path is not None and kb_manifest_path.exists():
            extra_artifacts["kb_index_manifest_json"] = str(kb_manifest_path)
        if run_paths["kb_index_state"].exists():
            extra_artifacts["kb_index_state_json"] = str(run_paths["kb_index_state"])
        for key, path in ranking_paths.items():
            extra_artifacts[f"ranking_{key}"] = str(path)
        for test_id, paths in test_output_paths.items():
            for kind, path in paths.items():
                extra_artifacts[f"tests_outputs.{test_id}.{kind}"] = str(path)

        report_payload = build_report_json_payload(
            run_id=run_id,
            dataset_hash=dataset_hash,
            out_dir=settings["out_dir"],
            summary={
                "overall_status": overall_status,
                "tests_total": len(test_runs),
                "tests_ok": tests_ok,
                "tests_error": tests_error,
                "tests_timeout": tests_timeout,
                "findings_total": findings_total,
                "ranking_entities": len(ranking_rows),
            },
            ranking=ranking_rows[:top_k],
            top_k=top_k,
            test_runs=test_runs,
            artifact_paths=extra_artifacts,
            errors=[],
            metadata_extra={
                "loaded_tables": loaded_tables,
                "input_zip": settings["input_zip"],
                "weights_config": settings["weights_config"],
                "out_dir": settings["out_dir"],
                "select_tests": settings["select_tests"] or [],
                "select_fraud_types": settings["select_fraud_types"] or [],
                "select_tags": settings["select_tags"] or [],
                "table_stats": table_stats,
                "test_report_cards": test_report_cards,
                "red_flags_activated": red_flags_activated,
                "kb_index_enabled": settings["kb_index_enabled"],
                "kb_index_status": kb_index_status,
                "kb_index_error": kb_index_error,
                "kb_sources_config": settings["kb_sources_config"],
                "kb_chunking_config": settings["kb_chunking_config"],
                "kb_chroma_config": settings["kb_chroma_config"],
                "llm_mode": settings["llm_mode"],
                "process_family": settings["process_family"],
            },
        )
        report_json_path = write_report_json(
            output_path=run_paths["report_json"],
            payload=report_payload,
        )
        report_md_path = write_report_markdown_from_report_json(
            report_json_path=report_json_path,
            report_md_path=run_paths["report_md"],
        )
        render_report_markdown_to_html(
            report_md_path=report_md_path,
            report_html_path=run_paths["report_html"],
        )
        write_or_update_report_markdown_with_data_validation(
            report_md_path=report_md_path,
            data_validation_report_path=validation_outcome.report_path,
        )
        write_or_update_report_markdown_with_drilldown_instructions(
            report_md_path=report_md_path,
            run_id=run_id,
        )
        _write_run_structure_manifest(run_id=run_id, run_dir=run_dir, paths=run_paths)

        missing_links = validate_report_artifact_paths_exist(
            report_payload=report_payload,
            base_path=".",
        )
        if missing_links:
            logger.log_warning(
                "Reporte con enlaces de artefactos faltantes",
                missing_artifacts=missing_links,
            )
            print(
                f"ERROR: report.json contiene {len(missing_links)} artifact_paths inexistentes",
                file=sys.stderr,
            )
            return 1
        try:
            validate_required_run_outputs(run_dir=run_dir)
        except RunOutputValidationError as exc:
            logger.log_error("Validación de outputs obligatorios falló", error=str(exc))
            print(f"ERROR: outputs obligatorios incompletos: {exc}", file=sys.stderr)
            return 1

        if str(settings.get("pipeline_mode", "deterministic")).strip().lower() == "graph":
            graph_code = _execute_graph_pipeline_in_workspace(
                settings=settings,
                run_id=run_id,
                workspace_input_zip=Path(settings["input_zip"]),
                process_scope=str(settings.get("process_scope", "p2p")).strip(),
                artifact_hash=artifact_hash,
            )
            if graph_code != 0:
                logger.log_error("Ejecución grafo falló tras pipeline base", error=str(graph_code))
                return int(graph_code)

        logger.log_ingest_end(
            status=overall_status,
            tables_loaded=len(loaded_tables),
            tests_total=len(test_runs),
            findings_total=findings_total,
            run_dir=str(run_dir),
        )
        print(
            "OK: run completado "
            f"(run_id={run_id}, tests={len(test_runs)}, findings={findings_total}, out={run_dir})"
        )
        return 0
    except CatalogValidationError as exc:
        logger.log_error("Validación de catálogo RF13 falló", error=str(exc))
        print(f"ERROR: validación catálogo falló: {exc}", file=sys.stderr)
        return 1
    except O2CTransformError as exc:
        logger.log_error("Transformación O2C falló", error=str(exc))
        print(f"ERROR: transformación O2C falló: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        logger.log_error("Pipeline run falló", error=str(exc))
        print(f"ERROR: pipeline run falló: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="erp-fraud")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-dictionary",
        help="Valida que los campos usados por tests estén documentados",
    )
    validate_parser.add_argument(
        "--dictionary",
        default="data_dictionary.json",
        help="Ruta al data_dictionary.json (default: data_dictionary.json)",
    )
    validate_parser.add_argument(
        "--catalog",
        default="tests/catalog",
        help="Ruta al catálogo de tests (default: tests/catalog)",
    )
    validate_parser.add_argument(
        "--output-json",
        action="store_true",
        help="Imprime resumen en JSON en stdout",
    )
    validate_parser.set_defaults(handler=_run_validate_dictionary)

    drilldown_parser = subparsers.add_parser(
        "drilldown",
        help="Devuelve filas origen para un hallazgo usando test_id + entity_key",
    )
    drilldown_parser.add_argument("--run-id", required=True, help="Run ID de referencia")
    drilldown_parser.add_argument("--test-id", required=True, help="Test ID del catálogo")
    drilldown_parser.add_argument(
        "--entity-key",
        required=True,
        help="Clave de entidad en formato key=value|key2=value2",
    )
    drilldown_parser.add_argument(
        "--db-path",
        default="erp.duckdb",
        help="Ruta a DuckDB (default: erp.duckdb)",
    )
    drilldown_parser.add_argument(
        "--schema-name",
        default="main",
        help="Schema DuckDB (default: main)",
    )
    drilldown_parser.add_argument(
        "--table-name",
        default="fraud_1",
        help="Tabla base para drilldown (default: fraud_1)",
    )
    drilldown_parser.add_argument(
        "--limit-rows",
        type=int,
        default=200,
        help="Límite de filas de salida (default: 200, max cap interno 200)",
    )
    drilldown_parser.add_argument(
        "--order-direction",
        default="ASC",
        choices=["ASC", "DESC", "asc", "desc"],
        help="Orden de salida (ASC|DESC, default: ASC)",
    )
    drilldown_parser.add_argument(
        "--transaktionsart",
        default=None,
        help="Filtro opcional permitido por plantilla (Transaktionsart)",
    )
    drilldown_parser.add_argument(
        "--output",
        default=None,
        help="Ruta de salida JSON; si no se informa, imprime a stdout",
    )
    drilldown_parser.add_argument(
        "--save-default",
        action="store_true",
        help="Guarda en run_results/<run_id>/drilldown_<test_id>.json",
    )
    drilldown_parser.set_defaults(handler=_run_drilldown)

    list_runs_parser = subparsers.add_parser(
        "list-runs",
        help="Lista runs persistidos con resumen (RF16)",
    )
    list_runs_parser.add_argument(
        "--base-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Directorio base de runs (default: {DEFAULT_OUT_DIR})",
    )
    list_runs_parser.add_argument(
        "--output-json",
        action="store_true",
        help="Imprime salida en JSON",
    )
    list_runs_parser.set_defaults(handler=_run_list_runs)

    compare_runs_parser = subparsers.add_parser(
        "compare-runs",
        help="Compara runs y genera análisis RF16 (JSON + MD) con recomendaciones",
    )
    compare_runs_parser.add_argument(
        "run_ids",
        nargs="*",
        help="Run IDs a comparar (1..N). Si se omiten, usar --auto-latest-p2p-o2c",
    )
    compare_runs_parser.add_argument(
        "--base-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Directorio base de runs (default: {DEFAULT_OUT_DIR})",
    )
    compare_runs_parser.add_argument(
        "--auto-latest-p2p-o2c",
        action="store_true",
        help="Selecciona automáticamente el último run p2p y el último o2c",
    )
    compare_runs_parser.add_argument(
        "--analysis-id",
        default=None,
        help="ID del análisis RF16 (default: autogenerado)",
    )
    compare_runs_parser.set_defaults(handler=_run_compare_runs)

    run_parser = subparsers.add_parser(
        "run",
        help="Ejecuta pipeline completo: ingesta -> validación -> tests -> ranking -> reporte",
    )
    run_parser.add_argument(
        "--input-zip",
        default=None,
        help=f"Ruta al zip de entrada (default: {DEFAULT_RUN_INPUT_ZIP})",
    )
    run_parser.add_argument(
        "--run-id",
        default=None,
        help="Run ID opcional (default: autogenerado UTC)",
    )
    run_parser.add_argument(
        "--out-dir",
        default=None,
        help=f"Directorio raíz de salidas por run (default: {DEFAULT_OUT_DIR})",
    )
    run_parser.add_argument(
        "--db-path",
        default=None,
        help=f"Ruta a DuckDB (default: {DEFAULT_DB_PATH})",
    )
    run_parser.add_argument(
        "--schema-name",
        default=None,
        help=f"Schema DuckDB para validación/tests (default: {DEFAULT_SCHEMA_NAME})",
    )
    run_parser.add_argument(
        "--table-name",
        default=None,
        help=f"Tabla base para ejecución de tests del catálogo (default: {DEFAULT_TABLE_NAME})",
    )
    run_parser.add_argument(
        "--catalog",
        default=None,
        help=f"Ruta al catálogo de tests (default: {DEFAULT_CATALOG_PATH})",
    )
    run_parser.add_argument(
        "--weights-config",
        default=None,
        help=f"Ruta a configuración de pesos del ranking (default: {DEFAULT_WEIGHTS_CONFIG})",
    )
    run_parser.add_argument(
        "--timeout-ms",
        type=int,
        default=None,
        help="Timeout opcional por test en milisegundos",
    )
    run_parser.add_argument(
        "--select-tests",
        default=None,
        help="Lista de test_ids separada por coma (ej: TST-A,TST-B)",
    )
    run_parser.add_argument(
        "--select-fraud-types",
        default=None,
        help="Filtra tests por fraud_type (lista separada por coma, ej: duplicate_payment,amount_anomaly)",
    )
    run_parser.add_argument(
        "--select-tags",
        default=None,
        help="Filtra tests por tags de catálogo (lista separada por coma, ej: p2p,acfe)",
    )
    run_parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Top-k de ranking (override sobre config/weights.yaml)",
    )
    run_parser.add_argument(
        "--config",
        default=None,
        help="Fichero JSON/YAML con parámetros de run",
    )
    run_parser.add_argument(
        "--sample-top-n",
        type=int,
        default=None,
        help=f"Top N para sample por test (default: {DEFAULT_SAMPLE_TOP_N})",
    )
    run_parser.add_argument(
        "--kb-index-enabled",
        dest="kb_index_enabled",
        action="store_true",
        default=None,
        help="Activa reconstrucción automática de índice KB (incremental)",
    )
    run_parser.add_argument(
        "--no-kb-index",
        dest="kb_index_enabled",
        action="store_false",
        help="Desactiva reconstrucción automática de índice KB",
    )
    run_parser.add_argument(
        "--kb-sources-config",
        default=None,
        help=f"Config de fuentes KB (default: {DEFAULT_KB_SOURCES_CONFIG})",
    )
    run_parser.add_argument(
        "--kb-chunking-config",
        default=None,
        help=f"Config de chunking KB (default: {DEFAULT_KB_CHUNKING_CONFIG})",
    )
    run_parser.add_argument(
        "--kb-chroma-config",
        default=None,
        help=f"Config de Chroma KB (default: {DEFAULT_KB_CHROMA_CONFIG})",
    )
    run_parser.add_argument(
        "--llm-mode",
        default=None,
        choices=["stub", "real"],
        help="Modo de nodos LLM del grafo (stub|real). Default: stub",
    )
    run_parser.add_argument(
        "--pipeline-mode",
        default=None,
        choices=["deterministic", "graph"],
        help="Modo de ejecución del comando run (deterministic|graph). Default: deterministic",
    )
    run_parser.add_argument(
        "--process-family",
        default=None,
        choices=["p2p", "o2c"],
        help="Familia de proceso del run (p2p|o2c). Default: p2p",
    )
    run_parser.add_argument(
        "--o2c-canonical-schema-config",
        default=None,
        help=f"Config schema O2C (default: {DEFAULT_O2C_CANONICAL_SCHEMA_CONFIG})",
    )
    run_parser.add_argument(
        "--o2c-identity-config",
        default=None,
        help=f"Config identidad/dedup O2C (default: {DEFAULT_O2C_IDENTITY_CONFIG})",
    )
    run_parser.add_argument(
        "--o2c-mapping-config",
        default=None,
        help=f"Config mapping raw->canónico O2C (default: {DEFAULT_O2C_MAPPING_CONFIG})",
    )
    run_parser.add_argument(
        "--o2c-target-schema",
        default=None,
        help=f"Schema destino O2C en DuckDB (default: {DEFAULT_O2C_TARGET_SCHEMA})",
    )
    run_parser.set_defaults(handler=_run_pipeline)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
