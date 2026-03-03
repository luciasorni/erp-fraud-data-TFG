# Arquitectura (Fase 1)

## Objetivo

Construir una base reproducible para ejecutar tests de fraude sobre datos ERP P2P.

## Flujo actual

1. Entrada: `erp_fraud_data.zip` (solo `joint_datasets/`)
2. Ingesta:
   - localizar y validar ficheros esperados
   - cargar CSV/Parquet a `pandas`
   - limpieza técnica y normalización de tipos
3. Persistencia:
   - cargar tablas en `erp.duckdb`
   - registrar métricas por tabla (`rows_loaded`, `duration_ms`)
4. Artefactos de trazabilidad:
   - `dataset_hash`
   - `schema_summary.json`
   - `run_metadata.json`
   - `ingest_logs.jsonl`

## Módulos clave

- `src/erp_fraud/ingest/`: lectura, validación y preparación de datos
- `src/erp_fraud/storage/`: DuckDB, artefactos, diccionario y validaciones
- `src/erp_fraud/cli/`: comandos de terminal (`validate-dictionary`)

## Decisiones

- Fase 1 centrada en P2P y `joint_datasets`.
- `run_results/<run_id>/` como carpeta de evidencia local por ejecución.
- Validaciones y diccionario antes de escalar catálogo de tests (`RF03`).
