# RF11-07 — Integración `process_family` (`p2p|o2c`) en config/metadata

Fecha: 2026-04-10  
Estado: Cerrado

## 1) Objetivo

Separar explícitamente ejecuciones P2P y O2C en configuración y metadatos, sin romper compatibilidad del flujo actual.

## 2) Cambios implementados

1. Default centralizado:
- `src/erp_fraud/config/run_defaults.py`
  - `DEFAULT_PROCESS_FAMILY = "p2p"`

2. Export de configuración:
- `src/erp_fraud/config/__init__.py`
  - `DEFAULT_PROCESS_FAMILY` añadido al módulo público.

3. CLI `run`:
- `src/erp_fraud/cli/main.py`
  - nuevo flag `--process-family {p2p,o2c}`
  - normalización con fallback seguro a `p2p`
  - inclusión en `ingest_start` log, `run_metadata.json` y `report.metadata_extra`.

4. Metadatos de run:
- `src/erp_fraud/storage/run_metadata.py`
  - `process_family` añadido a `build_run_metadata` / `write_run_metadata_json`
  - validación estricta de valores permitidos (`p2p|o2c`).

## 3) Compatibilidad hacia atrás

1. Si no se informa `--process-family`, el comportamiento es idéntico al actual (`p2p` por defecto).
2. No se modifica lógica de ejecución de tests P2P existentes.

## 4) Validación

Tests actualizados:

1. `tests/test_rf13_catalog_selection.py`
  - parseo de `--process-family o2c`.

2. `tests/test_rf15e_cli_kb_integration.py`
  - default `process_family == "p2p"` en resolución de settings.

3. `tests/test_rf01_ingest_storage.py`
  - `run_metadata` incluye `process_family`.

## 5) Siguiente tarea

`RF11-08` — conectar este selector a la orquestación/ingesta para soportar run O2C completo sin romper P2P.
