"""Limpieza técnica mínima de dataframes (sin lógica de fraude)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
from pandas.api.types import is_string_dtype


NULL_TOKENS_DEFAULT = frozenset(
    {
        "",
        " ",
        "null",
        "none",
        "nan",
        "n/a",
        "na",
        "<na>",
    }
)


@dataclass(frozen=True)
class TechnicalCleaningSummary:
    """Resumen básico de la limpieza técnica aplicada."""

    columns_processed: tuple[str, ...]
    trimmed_cells: int
    nulls_normalized: int


def _clean_string_series(
    series: pd.Series,
    *,
    null_tokens: frozenset[str],
) -> tuple[pd.Series, int, int]:
    original = series.astype("string")
    stripped = original.str.strip()

    trimmed_mask = (
        original.notna()
        & stripped.notna()
        & (original != stripped)
    )
    trimmed_count = int(trimmed_mask.sum())

    lowered = stripped.str.lower()
    null_mask = stripped.notna() & lowered.isin(null_tokens)
    null_count = int(null_mask.sum())

    cleaned = stripped.mask(null_mask, pd.NA)
    return cleaned, trimmed_count, null_count


def limpiar_tecnicamente_dataframe(
    df: pd.DataFrame,
    *,
    columns: Iterable[str] | None = None,
    only_string_like: bool = True,
    null_tokens: Iterable[str] = NULL_TOKENS_DEFAULT,
) -> tuple[pd.DataFrame, TechnicalCleaningSummary]:
    """Aplica limpieza técnica mínima.

    Incluye:
    - trim en strings
    - normalización de nulls textuales (`''`, `null`, `nan`, etc.) a `pd.NA`
    """
    cleaned_df = df.copy()
    null_tokens_normalized = frozenset(token.strip().lower() for token in null_tokens)

    target_columns = list(columns) if columns is not None else list(cleaned_df.columns)
    processed_columns: list[str] = []
    trimmed_total = 0
    nulls_total = 0

    for col in target_columns:
        if col not in cleaned_df.columns:
            continue
        if only_string_like and not is_string_dtype(cleaned_df[col]):
            continue

        cleaned_series, trimmed_count, null_count = _clean_string_series(
            cleaned_df[col],
            null_tokens=null_tokens_normalized,
        )
        cleaned_df[col] = cleaned_series
        processed_columns.append(col)
        trimmed_total += trimmed_count
        nulls_total += null_count

    summary = TechnicalCleaningSummary(
        columns_processed=tuple(processed_columns),
        trimmed_cells=trimmed_total,
        nulls_normalized=nulls_total,
    )
    return cleaned_df, summary
