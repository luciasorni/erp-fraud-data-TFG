"""Cálculo de hash reproducible del dataset dentro del zip para detectar cambios en el contenido entre ejecuciones."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from zipfile import ZipFile

from .zip_reader import listar_ficheros_joint_datasets, localizar_joint_datasets


@dataclass(frozen=True)
class DatasetHashResult:
    """Resultado del cálculo de hash del dataset."""

    dataset_hash: str
    algorithm: str
    files_hashed: int
    total_bytes: int
    scope: str = "joint_datasets"


def calcular_dataset_hash(zip_path: str | Path) -> DatasetHashResult:
    """Calcula un hash reproducible del contenido de `joint_datasets/` dentro del zip.

    Estrategia:
    - orden estable por nombre de fichero
    - mezcla nombre relativo + tamaño + contenido (bytes)
    """
    zip_path = Path(zip_path)
    prefix = localizar_joint_datasets(zip_path)
    file_names = listar_ficheros_joint_datasets(zip_path)

    digest = hashlib.sha256()
    total_bytes = 0

    with ZipFile(zip_path) as zf:
        for file_name in file_names:
            member = f"{prefix}{file_name}"
            raw_bytes = zf.read(member)
            total_bytes += len(raw_bytes)

            # Delimitadores explícitos para evitar ambigüedades al concatenar.
            digest.update(b"FILE\x00")
            digest.update(file_name.encode("utf-8"))
            digest.update(b"\x00SIZE\x00")
            digest.update(str(len(raw_bytes)).encode("ascii"))
            digest.update(b"\x00CONTENT\x00")
            digest.update(raw_bytes)
            digest.update(b"\x00END\x00")

    return DatasetHashResult(
        dataset_hash=digest.hexdigest(),
        algorithm="sha256",
        files_hashed=len(file_names),
        total_bytes=total_bytes,
    )
