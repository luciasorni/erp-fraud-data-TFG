"""Validación de esquema de resultados por test (RF05-02)."""

from __future__ import annotations

from typing import Any

import pandas as pd


RESULT_DF_REQUIRED_COLUMNS: tuple[str, ...] = (
    "entity_key",
    "keys",
    "evidence_columns",
    "metrics",
)


def _fail(message: str) -> None:
    raise ValueError(message)


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing = [col for col in RESULT_DF_REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        _fail(
            "ResultSchema inválido: faltan columnas obligatorias "
            f"{missing}. Columnas presentes: {list(df.columns)}"
        )


def _validate_entity_key(df: pd.DataFrame) -> None:
    invalid = []
    for idx, value in df["entity_key"].items():
        if not isinstance(value, str) or not value.strip():
            invalid.append(int(idx))
    if invalid:
        _fail(
            "ResultSchema inválido: 'entity_key' debe ser string no vacío. "
            f"Filas inválidas: {invalid[:20]}"
        )


def _validate_keys(df: pd.DataFrame) -> None:
    invalid = []
    for idx, value in df["keys"].items():
        if not isinstance(value, dict) or len(value) == 0:
            invalid.append(int(idx))
    if invalid:
        _fail(
            "ResultSchema inválido: 'keys' debe ser objeto/dict no vacío. "
            f"Filas inválidas: {invalid[:20]}"
        )


def _validate_evidence_columns(df: pd.DataFrame) -> None:
    invalid = []
    for idx, value in df["evidence_columns"].items():
        if not isinstance(value, list) or len(value) == 0:
            invalid.append(int(idx))
            continue
        if not all(isinstance(col, str) and col.strip() for col in value):
            invalid.append(int(idx))
    if invalid:
        _fail(
            "ResultSchema inválido: 'evidence_columns' debe ser lista no vacía de strings. "
            f"Filas inválidas: {invalid[:20]}"
        )


def _validate_metrics(df: pd.DataFrame) -> None:
    invalid = []
    for idx, value in df["metrics"].items():
        if not isinstance(value, dict):
            invalid.append(int(idx))
    if invalid:
        _fail(
            "ResultSchema inválido: 'metrics' debe ser objeto/dict. "
            f"Filas inválidas: {invalid[:20]}"
        )


def validate_result_schema(df: Any) -> None:
    """Valida un DataFrame de hallazgos; lanza ValueError si no cumple esquema."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("validate_result_schema(df): df debe ser pandas.DataFrame")

    _validate_required_columns(df)
    _validate_entity_key(df)
    _validate_keys(df)
    _validate_evidence_columns(df)
    _validate_metrics(df)

