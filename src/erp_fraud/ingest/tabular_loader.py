"""Carga robusta de ficheros tabulares (CSV/Parquet) del dataset."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pyarrow.parquet as pq

from .zip_reader import localizar_joint_datasets

CSV_ENCODING_CANDIDATES = ("utf-8", "utf-8-sig", "latin-1", "cp1252")
CSV_SEPARATOR_CANDIDATES = (",", ";", "\t", "|")


class TabularLoadError(ValueError):
    """Error de carga/parseo de un fichero tabular."""


def _detectar_separador(sample_text: str) -> str:
    """Intenta detectar el separador CSV a partir de una muestra."""
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters="".join(CSV_SEPARATOR_CANDIDATES))
        return dialect.delimiter
    except csv.Error:
        return ","


def _leer_csv_bytes(
    raw_bytes: bytes,
    *,
    dtype: str | dict[str, str] | None = "string",
    sep: str | None = None,
) -> pd.DataFrame:
    last_error: Exception | None = None

    for encoding in CSV_ENCODING_CANDIDATES:
        try:
            sample_text = raw_bytes[:8192].decode(encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

        detected_sep = sep or _detectar_separador(sample_text)
        for engine in ("c", "python"):
            kwargs = {
                "encoding": encoding,
                "sep": detected_sep,
                "dtype": dtype,
                "engine": engine,
            }
            if engine == "c":
                kwargs["low_memory"] = False
            try:
                return pd.read_csv(io.BytesIO(raw_bytes), **kwargs)
            except Exception as exc:  # pandas puede lanzar diferentes tipos
                last_error = exc
                continue

    raise TabularLoadError(
        "No se pudo leer el CSV con los encodings/separadores configurados"
    ) from last_error


def _leer_parquet_bytes(raw_bytes: bytes) -> pd.DataFrame:
    try:
        table = pq.read_table(io.BytesIO(raw_bytes))
        return table.to_pandas()
    except Exception as exc:
        raise TabularLoadError("No se pudo leer el fichero Parquet") from exc


def cargar_fichero_tabular_desde_zip(
    zip_path: str | Path,
    file_name: str,
    *,
    dtype: str | dict[str, str] | None = "string",
    sep: str | None = None,
) -> pd.DataFrame:
    """Carga un CSV/Parquet desde `joint_datasets/` del zip a pandas."""
    prefix = localizar_joint_datasets(zip_path)
    member_path = f"{prefix}{file_name}"
    suffix = Path(file_name).suffix.lower()

    with ZipFile(zip_path) as zf:
        try:
            raw_bytes = zf.read(member_path)
        except KeyError as exc:
            raise FileNotFoundError(
                f"No existe '{file_name}' dentro de {prefix} en el zip {zip_path}"
            ) from exc

    if suffix == ".csv":
        return _leer_csv_bytes(raw_bytes, dtype=dtype, sep=sep)
    if suffix == ".parquet":
        return _leer_parquet_bytes(raw_bytes)

    raise TabularLoadError(
        f"Extensión no soportada para carga tabular: '{suffix or '<sin extensión>'}'"
    )
