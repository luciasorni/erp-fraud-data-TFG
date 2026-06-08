# Arquitectura (Fase 1, histórico)

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
5. Catálogo de tests (RF03):
   - definir y validar `TestSpec` en `tests/catalog`
   - ejecutar tests iniciales P2P sobre DuckDB
   - devolver salida estándar por test

## Módulos clave

- `src/erp_fraud/ingest/`: lectura, validación y preparación de datos
- `src/erp_fraud/storage/`: DuckDB, artefactos, diccionario y validaciones
- `src/erp_fraud/cli/`: comandos de terminal (`validate-dictionary`)
- `src/erp_fraud/catalog/`: esquema, loader/validador y ejecución de tests de catálogo

## Decisiones

- Fase 1 centrada en P2P y `joint_datasets`.
- `run_results/<run_id>/` como carpeta de evidencia local por ejecución.
- Validaciones y diccionario como prerequisito de ejecución de catálogo.
- Catálogo RF03 limitado a 2 tests iniciales; el motor robusto multi-test se amplía en RF04.
