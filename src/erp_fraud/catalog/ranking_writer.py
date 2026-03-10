"""Persistencia de ranking agregado (RF07-04)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sort_ranking_rows_stable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Orden estable de ranking por score y empate reproducible."""
    normalized = [dict(row) for row in rows]

    def _sort_key(row: dict[str, Any]) -> tuple[float, str, str]:
        score_total = row.get("score_total", 0.0)
        try:
            score_value = float(score_total)
        except (TypeError, ValueError):
            score_value = 0.0
        entity_key = str(row.get("entity_key", ""))
        row_part = _stable_json(row)
        return (-score_value, entity_key, row_part)

    return sorted(normalized, key=_sort_key)


def write_ranking_json(
    *,
    output_path: str | Path,
    ranking_rows: list[dict[str, Any]],
    top_k: int | None = None,
) -> Path:
    """Escribe ranking.json con orden estable."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sort_ranking_rows_stable(ranking_rows)
    if top_k is not None:
        if top_k <= 0:
            raise ValueError("top_k debe ser > 0")
        sorted_rows = sorted_rows[:top_k]
    payload = {
        "top_k": int(top_k) if top_k is not None else None,
        "row_count": len(sorted_rows),
        "ranking": sorted_rows,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_ranking_parquet(
    *,
    output_path: str | Path,
    ranking_rows: list[dict[str, Any]],
    top_k: int | None = None,
) -> Path:
    """Escribe ranking.parquet con orden estable."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sort_ranking_rows_stable(ranking_rows)
    if top_k is not None:
        if top_k <= 0:
            raise ValueError("top_k debe ser > 0")
        sorted_rows = sorted_rows[:top_k]
    df = pd.DataFrame(sorted_rows) if sorted_rows else pd.DataFrame()
    try:
        df.to_parquet(path, index=False)
    except Exception as exc:
        raise RuntimeError(
            "No se pudo escribir ranking.parquet. Instala pyarrow/fastparquet o usa JSON."
        ) from exc
    return path


def write_ranking_outputs(
    *,
    run_dir: str | Path,
    ranking_rows: list[dict[str, Any]],
    formats: tuple[str, ...] = ("json",),
    top_k: int | None = None,
) -> dict[str, str]:
    """Persistencia estándar de ranking en carpeta de run."""
    allowed_formats = {"json", "parquet"}
    unknown = [fmt for fmt in formats if fmt not in allowed_formats]
    if unknown:
        raise ValueError(f"formatos no soportados: {unknown}")

    base = Path(run_dir)
    base.mkdir(parents=True, exist_ok=True)

    written: dict[str, str] = {}
    if "json" in formats:
        json_path = write_ranking_json(
            output_path=base / "ranking.json",
            ranking_rows=ranking_rows,
            top_k=top_k,
        )
        written["json"] = str(json_path)

    if "parquet" in formats:
        parquet_path = write_ranking_parquet(
            output_path=base / "ranking.parquet",
            ranking_rows=ranking_rows,
            top_k=top_k,
        )
        written["parquet"] = str(parquet_path)

    return written
