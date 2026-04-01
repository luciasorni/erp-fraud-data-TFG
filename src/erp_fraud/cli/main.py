"""CLI principal del proyecto ERP Fraud."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

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
    load_table_to_duckdb_with_stats,
    run_technical_validation_before_tests,
    write_or_update_report_markdown_with_data_validation,
    write_or_update_report_markdown_with_drilldown_instructions,
    write_report_json,
    write_report_markdown_from_report_json,
    render_report_markdown_to_html,
    validate_report_artifact_paths_exist,
    write_run_metadata_json,
    write_schema_summary_json,
)
from ..storage.data_dictionary import DataDictionaryCompletenessError, check_dictionary_completeness
from ..storage.paths import ruta_run
from ..storage.report_json import build_report_json_payload
from ..config import (
    DEFAULT_CATALOG_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_KB_CHROMA_CONFIG,
    DEFAULT_KB_CHUNKING_CONFIG,
    DEFAULT_KB_ENABLED,
    DEFAULT_KB_SOURCES_CONFIG,
    DEFAULT_OUT_DIR,
    DEFAULT_RUN_INPUT_ZIP,
    DEFAULT_SAMPLE_TOP_N,
    DEFAULT_SCHEMA_NAME,
    DEFAULT_TABLE_NAME,
    DEFAULT_WEIGHTS_CONFIG,
)


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


def _safe_table_name_from_file(file_name: str) -> str:
    stem = Path(file_name).stem.strip()
    if not stem:
        raise ValueError(f"Nombre de fichero inválido para tabla: {file_name}")
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in stem)


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
        "weights_config": str(_pick("weights_config", DEFAULT_WEIGHTS_CONFIG)),
        "timeout_ms": _pick("timeout_ms", None),
        "sample_top_n": int(_pick("sample_top_n", DEFAULT_SAMPLE_TOP_N)),
        "top_k": _pick("top_k", None),
        "select_tests": _parse_select_tests(_pick("select_tests", None)),
        "select_fraud_types": _parse_select_values(_pick("select_fraud_types", None)),
        "select_tags": _parse_select_values(_pick("select_tags", None)),
        "kb_index_enabled": bool(_pick("kb_index_enabled", DEFAULT_KB_ENABLED)),
        "kb_sources_config": str(_pick("kb_sources_config", DEFAULT_KB_SOURCES_CONFIG)),
        "kb_chunking_config": str(_pick("kb_chunking_config", DEFAULT_KB_CHUNKING_CONFIG)),
        "kb_chroma_config": str(_pick("kb_chroma_config", DEFAULT_KB_CHROMA_CONFIG)),
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


def _run_pipeline(args: argparse.Namespace) -> int:
    settings = _resolve_run_settings(args)
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
        )
        validar_ficheros_esperados_joint_datasets(settings["input_zip"])
        files = listar_ficheros_joint_datasets(settings["input_zip"])
        dataset_hash_result = calcular_dataset_hash(settings["input_zip"])
        dataset_hash = dataset_hash_result.dataset_hash

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
        )

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
            "schema_summary_json_run": str(schema_summary_path),
            "data_validation_report_json": str(validation_outcome.report_path),
            "test_runs_json": str(test_runs_path),
        }
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
