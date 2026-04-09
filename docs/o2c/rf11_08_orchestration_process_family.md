# RF11-08 — Orquestación `run` para O2C sin romper P2P

Fecha: 2026-04-10  
Estado: Cerrado (base operativa)

## 1) Objetivo

Habilitar ejecución O2C desde el comando unificado `erp-fraud run` separando flujos por `process_family`, manteniendo P2P como comportamiento por defecto.

## 2) Cambios de orquestación

Archivo principal:

- `src/erp_fraud/cli/main.py`

Implementado:

1. Nuevo modo de ejecución:
- `--process-family p2p|o2c`

2. Rama `p2p`:
- flujo actual intacto (`joint_datasets`, catálogo P2P, ranking/reporting como antes).

3. Rama `o2c`:
- no requiere `joint_datasets` en el zip,
- ejecuta transformación canónica O2C (`transform_raw_to_o2c_canonical`),
- ejecuta validación técnica O2C (`write_o2c_validation_report_json`),
- genera artefactos estándar de run (`run_metadata`, `schema_summary`, `report`, `run_structure`).

## 3) Nuevos flags `run` para O2C

1. `--o2c-canonical-schema-config`
2. `--o2c-identity-config`
3. `--o2c-target-schema`

Defaults:

- `config/canonical_schema_o2c.yaml`
- `config/o2c_entity_identity.yaml`
- `o2c`

## 4) Metadatos y trazabilidad

`run_metadata.json` y `report.metadata_extra` incluyen ahora:

1. `process_family`
2. `o2c_target_schema` (en modo O2C)
3. `o2c_transform_status`
4. `o2c_validation_summary`

## 5) Validación

Tests añadidos:

- `tests/test_rf11_o2c_cli_run.py`
  1. run `o2c` OK con fuentes mínimas.
  2. run `o2c` ERROR cuando faltan tablas `fail_fast`.

Regresión mantenida:

- tests existentes de P2P y scoring siguen pasando.

## 6) Limitación actual

La rama `o2c` asume que tablas raw SAP ya están en DuckDB (`main`).  
La carga completa `raw_data -> main` desde zip interno (nested zips/XLSX) sigue para siguiente iteración de ingest O2C.
