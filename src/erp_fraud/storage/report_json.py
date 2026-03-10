"""Estructura base de report.json para RF08."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_JSON_VERSION = "1.0.0"


def _utc_timestamp_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sorted_paths(value: dict[str, str] | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key, path in value.items():
        if not isinstance(key, str) or not key.strip():
            continue
        if path is None:
            continue
        cleaned[key.strip()] = str(path)
    return dict(sorted(cleaned.items(), key=lambda item: item[0]))


def _normalize_test_runs(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "test_id": str(item.get("test_id", "")),
                "version": str(item.get("version", "")),
                "status": str(item.get("status", "")),
                "duration_ms": int(item.get("duration_ms", 0) or 0),
                "error_summary": str(item.get("error_summary", "")),
            }
        )
    return sorted(normalized, key=lambda row: row["test_id"])


def _normalize_errors(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "scope": str(item.get("scope", "")),
                "code": str(item.get("code", "")),
                "message": str(item.get("message", "")),
            }
        )
    return sorted(normalized, key=lambda row: (row["scope"], row["code"], row["message"]))


def _build_errors_from_test_runs(
    test_runs: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not isinstance(test_runs, list):
        return []
    generated: list[dict[str, Any]] = []
    for item in test_runs:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).upper()
        if status not in {"ERROR", "TIMEOUT"}:
            continue
        test_id = str(item.get("test_id", ""))
        message = str(item.get("error_summary", "")).strip()
        if not message:
            message = f"{status} sin detalle"
        generated.append(
            {
                "scope": "test_run",
                "code": f"{status}:{test_id}",
                "message": message,
            }
        )
    return generated


def build_default_report_artifact_paths(
    *,
    run_id: str,
    out_dir: str | Path = "run_results",
    test_runs: list[dict[str, Any]] | None = None,
    sample_top_n: int = 20,
) -> dict[str, str]:
    """Construye rutas estándar de artefactos para report.json (RF08-05)."""
    if not run_id or not run_id.strip():
        raise ValueError("run_id debe ser string no vacío")
    if sample_top_n <= 0:
        raise ValueError("sample_top_n debe ser > 0")

    rid = run_id.strip()
    base_run = Path(out_dir) / rid
    paths: dict[str, str] = {
        "report_json": (base_run / "report.json").as_posix(),
        "report_md": (base_run / "report.md").as_posix(),
        "report_html": (base_run / "report.html").as_posix(),
        "ranking_json": (base_run / "ranking.json").as_posix(),
        "ranking_parquet": (base_run / "ranking.parquet").as_posix(),
        "test_runs_json": (base_run / "test_runs.json").as_posix(),
        "data_validation_report_json": (base_run / "data_validation_report.json").as_posix(),
        "schema_summary_json": "schema_summary.json",
        "data_dictionary_json": "data_dictionary.json",
        "data_dictionary_md": "data_dictionary.md",
    }

    if isinstance(test_runs, list):
        for row in test_runs:
            if not isinstance(row, dict):
                continue
            test_id = str(row.get("test_id", "")).strip()
            if not test_id:
                continue
            test_dir = base_run / "tests_outputs" / test_id
            prefix = f"tests_outputs.{test_id}"
            paths[f"{prefix}.findings_jsonl"] = (test_dir / "findings.jsonl").as_posix()
            paths[f"{prefix}.findings_parquet"] = (test_dir / "findings.parquet").as_posix()
            paths[f"{prefix}.sample_json"] = (test_dir / f"sample_top{sample_top_n}.json").as_posix()

    return dict(sorted(paths.items(), key=lambda item: item[0]))


def build_report_json_payload(
    *,
    run_id: str,
    dataset_hash: str,
    summary: dict[str, Any] | None = None,
    ranking: list[dict[str, Any]] | None = None,
    top_k: int | None = None,
    test_runs: list[dict[str, Any]] | None = None,
    artifact_paths: dict[str, str] | None = None,
    errors: list[dict[str, Any]] | None = None,
    metadata_extra: dict[str, Any] | None = None,
    out_dir: str | Path = "run_results",
) -> dict[str, Any]:
    """Construye estructura estable de report.json (RF08-01)."""
    if not run_id or not run_id.strip():
        raise ValueError("run_id debe ser string no vacío")
    if not dataset_hash or not dataset_hash.strip():
        raise ValueError("dataset_hash debe ser string no vacío")

    ranking_rows = ranking if isinstance(ranking, list) else []
    summary_payload = {
        "overall_status": str((summary or {}).get("overall_status", "UNKNOWN")),
        "tests_total": int((summary or {}).get("tests_total", 0) or 0),
        "tests_ok": int((summary or {}).get("tests_ok", 0) or 0),
        "tests_error": int((summary or {}).get("tests_error", 0) or 0),
        "tests_timeout": int((summary or {}).get("tests_timeout", 0) or 0),
        "findings_total": int((summary or {}).get("findings_total", 0) or 0),
        "ranking_entities": int((summary or {}).get("ranking_entities", len(ranking_rows)) or 0),
        "top_k": int(top_k) if top_k is not None else None,
    }

    default_artifacts = build_default_report_artifact_paths(
        run_id=run_id.strip(),
        out_dir=out_dir,
        test_runs=test_runs,
    )
    merged_artifacts = default_artifacts
    if isinstance(artifact_paths, dict):
        merged_artifacts = {**default_artifacts, **artifact_paths}

    normalized_input_errors = _normalize_errors(errors)
    generated_errors = _normalize_errors(_build_errors_from_test_runs(test_runs))
    merged_errors_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in normalized_input_errors + generated_errors:
        key = (str(row.get("scope", "")), str(row.get("code", "")), str(row.get("message", "")))
        merged_errors_map[key] = row
    merged_errors = list(merged_errors_map.values())
    merged_errors.sort(key=lambda row: (row["scope"], row["code"], row["message"]))

    payload: dict[str, Any] = {
        "report_version": REPORT_JSON_VERSION,
        "generated_at_utc": _utc_timestamp_iso(),
        "metadata": {
            "run_id": run_id.strip(),
            "dataset_hash": dataset_hash.strip(),
            "metadata_extra": dict(sorted((metadata_extra or {}).items(), key=lambda item: item[0])),
        },
        "summary": summary_payload,
        "ranking": {
            "top_k": int(top_k) if top_k is not None else None,
            "row_count": len(ranking_rows),
            "rows": ranking_rows,
        },
        "test_runs": _normalize_test_runs(test_runs),
        "artifact_paths": _sorted_paths(merged_artifacts),
        "errors": merged_errors,
    }
    return payload


def write_report_json(
    *,
    output_path: str | Path,
    payload: dict[str, Any],
) -> Path:
    """Escribe report.json con orden estable de claves."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def validate_report_artifact_paths_exist(
    *,
    report_payload: dict[str, Any],
    base_path: str | Path = ".",
) -> list[dict[str, str]]:
    """Valida que `artifact_paths` referencie solo ficheros existentes (RF08-07).

    Devuelve lista de rutas faltantes:
    - [{"artifact_key": "...", "path": "..."}]
    """
    if not isinstance(report_payload, dict):
        raise ValueError("report_payload debe ser un objeto")

    artifact_paths = report_payload.get("artifact_paths")
    if artifact_paths is None:
        return []
    if not isinstance(artifact_paths, dict):
        raise ValueError("artifact_paths debe ser objeto {clave: ruta}")

    root = Path(base_path)
    missing: list[dict[str, str]] = []
    for key, value in sorted(artifact_paths.items(), key=lambda item: str(item[0])):
        if not isinstance(key, str) or not key.strip():
            continue
        if not isinstance(value, str) or not value.strip():
            missing.append({"artifact_key": str(key), "path": str(value)})
            continue
        candidate = Path(value.strip())
        resolved = candidate if candidate.is_absolute() else (root / candidate)
        if not resolved.exists():
            missing.append({"artifact_key": key.strip(), "path": candidate.as_posix()})

    return missing


def validate_report_json_file_artifact_links(
    *,
    report_json_path: str | Path,
    base_path: str | Path = ".",
) -> list[dict[str, str]]:
    """Carga report.json y valida sus artifact_paths."""
    path = Path(report_json_path)
    if not path.exists():
        raise FileNotFoundError(f"No existe report.json: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("report.json debe contener un objeto")
    return validate_report_artifact_paths_exist(
        report_payload=payload,
        base_path=base_path,
    )
