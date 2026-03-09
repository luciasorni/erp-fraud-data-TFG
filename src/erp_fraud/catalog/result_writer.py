"""Serialización de resultados por test_id (RF05-04)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def _safe_test_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    if not cleaned:
        raise ValueError("test_id inválido para serialización")
    return cleaned


def _rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sort_result_rows_stable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Orden estable y reproducible de hallazgos.

    Prioridad de orden:
    1) `entity_key` ascendente si existe.
    2) `keys` serializado estable si existe.
    3) fallback al row completo serializado para estabilidad total.
    """
    normalized = [dict(row) for row in rows]

    def _sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
        entity_key = row.get("entity_key")
        keys = row.get("keys")
        entity_key_part = str(entity_key) if entity_key is not None else ""
        keys_part = _stable_json(keys) if keys is not None else ""
        row_part = _stable_json(row)
        return (entity_key_part, keys_part, row_part)

    return sorted(normalized, key=_sort_key)


def write_test_result_jsonl(
    *,
    output_path: str | Path,
    rows: list[dict[str, Any]],
) -> Path:
    """Escribe resultados en JSONL (una línea por hallazgo)."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sort_result_rows_stable(rows)
    with path.open("w", encoding="utf-8") as fh:
        for row in sorted_rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def write_test_result_parquet(
    *,
    output_path: str | Path,
    rows: list[dict[str, Any]],
) -> Path:
    """Escribe resultados en Parquet (un fichero por test)."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sort_result_rows_stable(rows)
    df = _rows_to_dataframe(sorted_rows)
    try:
        df.to_parquet(path, index=False)
    except Exception as exc:
        raise RuntimeError(
            "No se pudo escribir Parquet. Instala pyarrow/fastparquet o usa formato JSONL."
        ) from exc
    return path


def write_test_results_by_test_id(
    *,
    run_dir: str | Path,
    test_results: list[dict[str, Any]],
    formats: tuple[str, ...] = ("jsonl",),
    sample_top_n: int = 20,
) -> dict[str, dict[str, str]]:
    """Serializa resultados por test_id en `run_dir/tests_outputs/`."""
    base_dir = Path(run_dir) / "tests_outputs"
    base_dir.mkdir(parents=True, exist_ok=True)

    allowed_formats = {"jsonl", "parquet"}
    unknown = [fmt for fmt in formats if fmt not in allowed_formats]
    if unknown:
        raise ValueError(f"formatos no soportados: {unknown}")
    if sample_top_n <= 0:
        raise ValueError("sample_top_n debe ser > 0")

    written: dict[str, dict[str, str]] = {}
    for result in test_results:
        test_id = _safe_test_id(str(result.get("test_id", "")))
        rows = result.get("rows", [])
        if not isinstance(rows, list):
            raise ValueError(f"rows inválido para test_id={test_id}: debe ser list")

        test_dir = base_dir / test_id
        test_dir.mkdir(parents=True, exist_ok=True)
        written.setdefault(test_id, {})
        sorted_rows = sort_result_rows_stable(rows)

        if "jsonl" in formats:
            jsonl_path = write_test_result_jsonl(
                output_path=test_dir / "findings.jsonl",
                rows=sorted_rows,
            )
            written[test_id]["jsonl"] = str(jsonl_path)

        if "parquet" in formats:
            parquet_path = write_test_result_parquet(
                output_path=test_dir / "findings.parquet",
                rows=sorted_rows,
            )
            written[test_id]["parquet"] = str(parquet_path)

        sample_rows = sorted_rows[:sample_top_n]
        sample_path = test_dir / f"sample_top{sample_top_n}.json"
        sample_payload = {
            "test_id": test_id,
            "sample_size": len(sample_rows),
            "sample_limit": sample_top_n,
            "rows": sample_rows,
        }
        sample_path.write_text(
            json.dumps(sample_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written[test_id]["sample_json"] = str(sample_path)

    return written
