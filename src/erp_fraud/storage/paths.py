"""Convenciones de rutas de salida para ejecuciones del pipeline."""

from pathlib import Path

# Carpeta raíz donde se guardan los resultados por ejecución.
RUTA_SALIDA = Path("run_results")


def ruta_run(run_id: str) -> Path: # ruta_run es una función que toma un run_id como argumento y devuelve la ruta de la carpeta de resultados para ese run_id.
    """Devuelve la carpeta de resultados de un run: run_results/<run_id>/."""
    if not run_id or not run_id.strip():
        raise ValueError("run_id debe ser un string no vacío")
    return RUTA_SALIDA / run_id.strip()
