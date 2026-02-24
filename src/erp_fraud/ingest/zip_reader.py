"""Lectura de zips del dataset ERP Fraud."""

from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile


JOINT_DATASETS_DIRNAME = "joint_datasets"
EXPECTED_JOINT_DATASET_FILES = (
    "README.txt",
    "column_information.csv",
    "fraud_1.csv",
    "fraud_1_expls.csv",
    "fraud_2.csv",
    "fraud_2_expls.csv",
    "fraud_3.csv",
    "fraud_3_expls.csv",
    "normal_1.csv",
    "normal_2.csv",
)


class DatasetValidationError(ValueError):
    """Error de validación funcional/técnica del contenido del dataset."""


def localizar_joint_datasets(zip_path: str | Path) -> str:
    """Devuelve el prefijo dentro del zip que apunta a `joint_datasets/`."""
    try:
        with ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if name.startswith("__MACOSX/"):
                    continue
                parts = [part for part in name.split("/") if part]
                if JOINT_DATASETS_DIRNAME in parts:
                    idx = parts.index(JOINT_DATASETS_DIRNAME)
                    return "/".join(parts[: idx + 1]) + "/"
    except BadZipFile as exc:
        raise DatasetValidationError(f"Zip corrupto o no válido: {zip_path}") from exc

    raise FileNotFoundError(
        f"No se encontró la carpeta '{JOINT_DATASETS_DIRNAME}/' dentro del zip: {zip_path}"
    )


def listar_ficheros_joint_datasets(zip_path: str | Path) -> list[str]:
    """Lista ficheros dentro de `joint_datasets/` (rutas relativas a esa carpeta)."""
    prefix = localizar_joint_datasets(zip_path)

    try:
        with ZipFile(zip_path) as zf:
            files: list[str] = []
            for name in zf.namelist():
                if not name.startswith(prefix):
                    continue
                if name.startswith("__MACOSX/") or name.endswith("/"):
                    continue

                rel_name = name[len(prefix) :]
                if not rel_name:
                    continue
                files.append(rel_name)
    except BadZipFile as exc:
        raise DatasetValidationError(f"Zip corrupto o no válido: {zip_path}") from exc

    return sorted(files)


def validar_ficheros_esperados_joint_datasets(
    zip_path: str | Path,
    expected_files: tuple[str, ...] = EXPECTED_JOINT_DATASET_FILES,
) -> list[str]:
    """Valida que existan los ficheros esperados en `joint_datasets/`.

    Devuelve la lista real de ficheros si la validación pasa.
    """
    files = listar_ficheros_joint_datasets(zip_path)
    files_set = set(files)
    expected_set = set(expected_files)

    missing = sorted(expected_set - files_set)
    if missing:
        raise DatasetValidationError(
            "Faltan ficheros esperados en joint_datasets: " + ", ".join(missing)
        )

    return files
