"""Normalización de tipos sobre dataframes cargados desde el dataset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


DATE_KEYWORDS = (
    "date",
    "fecha",
    "datum",
    "timestamp",
)
AMOUNT_KEYWORDS_STRONG = (
    "betrag",
    "amount",
    "importe",
    "price",
    "precio",
    "cost",
    "skontobasis",
)
ID_KEYWORDS = (
    " id",
    "-id",
    "_id",
    "id",
    "nummer",
    "number",
    "belegnummer",
    "documento",
    "doc",
)


@dataclass(frozen=True)
class TypeNormalizationSummary:
    """Resumen de columnas normalizadas por categoría."""

    date_columns: tuple[str, ...]
    amount_columns: tuple[str, ...]
    id_columns: tuple[str, ...]


class TypeNormalizationError(ValueError):
    """Error de normalización de tipos con detalle de parseo."""


def _normalize_name(column_name: str) -> str:
    return column_name.strip().lower()


def _match_keywords(column_name: str, keywords: tuple[str, ...]) -> bool:
    normalized = _normalize_name(column_name)
    return any(keyword in normalized for keyword in keywords)


def _infer_columns(columns: Iterable[str], keywords: tuple[str, ...]) -> list[str]:
    return [col for col in columns if _match_keywords(col, keywords)]


def _looks_like_amount_column(column_name: str) -> bool:
    normalized = _normalize_name(column_name)
    if any(keyword in normalized for keyword in AMOUNT_KEYWORDS_STRONG):
        return True

    if "bewert" in normalized or "wertestring" in normalized:
        return False

    # Captura importes tipo "Gesamtwert"/"totalwert" evitando "Bewertung..."
    return normalized.endswith("wert") or " valor" in normalized


def _to_string_dtype(series: pd.Series) -> pd.Series:
    return series.astype("string")


def _to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=True)


def _to_float(series: pd.Series) -> pd.Series:
    text = (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", "", regex=True)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(text, errors="coerce")


def _count_parse_failures(original: pd.Series, parsed: pd.Series) -> int:
    original_text = original.astype("string").str.strip()
    original_non_empty = original_text.notna() & (original_text != "")
    parsed_invalid = parsed.isna()
    return int((original_non_empty & parsed_invalid).sum())


def normalizar_tipos_dataframe(
    df: pd.DataFrame,
    *,
    date_columns: Iterable[str] | None = None,
    amount_columns: Iterable[str] | None = None,
    id_columns: Iterable[str] | None = None,
    fail_on_parse_errors: bool = False,
) -> tuple[pd.DataFrame, TypeNormalizationSummary]:
    """Normaliza tipos mínimos del dataframe.

    Reglas:
    - Fechas: `datetime64[ns]` con `to_datetime(errors="coerce")`
    - Importes: `float` con `to_numeric(errors="coerce")`
    - IDs: `string` (preservar ceros a la izquierda y claves)

    Si no se proporcionan columnas explícitas, se infieren por heurística usando
    nombres de columna.
    """
    normalized_df = df.copy()

    inferred_date_cols = list(date_columns) if date_columns is not None else _infer_columns(df.columns, DATE_KEYWORDS)
    inferred_amount_cols = (
        list(amount_columns)
        if amount_columns is not None
        else [col for col in df.columns if _looks_like_amount_column(col)]
    )
    inferred_id_cols = list(id_columns) if id_columns is not None else _infer_columns(df.columns, ID_KEYWORDS)

    # Los IDs prevalecen: si una columna coincide en varias categorías se fuerza a string.
    date_cols = [col for col in inferred_date_cols if col in normalized_df.columns and col not in inferred_id_cols]
    amount_cols = [col for col in inferred_amount_cols if col in normalized_df.columns and col not in inferred_id_cols]
    id_cols = [col for col in inferred_id_cols if col in normalized_df.columns]

    parse_errors: list[str] = []

    for col in date_cols:
        parsed = _to_datetime(normalized_df[col])
        failures = _count_parse_failures(normalized_df[col], parsed)
        if fail_on_parse_errors and failures > 0:
            parse_errors.append(f"fecha:{col} ({failures} valores no parseables)")
        normalized_df[col] = parsed

    for col in amount_cols:
        parsed = _to_float(normalized_df[col])
        failures = _count_parse_failures(normalized_df[col], parsed)
        if fail_on_parse_errors and failures > 0:
            parse_errors.append(f"importe:{col} ({failures} valores no parseables)")
        normalized_df[col] = parsed

    for col in id_cols:
        normalized_df[col] = _to_string_dtype(normalized_df[col])

    if parse_errors:
        raise TypeNormalizationError(
            "Tipos no parseables detectados durante la normalización: "
            + "; ".join(parse_errors)
        )

    summary = TypeNormalizationSummary(
        date_columns=tuple(date_cols),
        amount_columns=tuple(amount_cols),
        id_columns=tuple(id_cols),
    )
    return normalized_df, summary
