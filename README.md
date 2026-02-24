# erp-fraud-data-TFG

Base del TFG para detección de fraude en ERP (fase inicial P2P) usando el dataset `ERP Fraud Data` y DuckDB.

## Alcance actual (Fase 1 - RF01 en progreso)

- Ingesta orientada a `joint_datasets/` (P2P, dataset plano)
- No se usa `raw_data/` en esta fase
- Carga a DuckDB local (`erp.duckdb`)
- Generación de artefactos reproducibles por ejecución:
  - `dataset_hash`
  - `schema_summary.json`
  - `run_metadata.json`
  - logs JSONL de ingesta

## Estructura relevante

- `src/erp_fraud/ingest/`: lectura del zip, validación, carga tabular, normalización y limpieza
- `src/erp_fraud/storage/`: DuckDB, rutas de salida, schema summary, run metadata y logging JSON
- `tests/`: tests unitarios de la base de ingesta/storage
- `run_results/<run_id>/`: salidas y evidencias de cada ejecución (local, no versionado)

## Qué está implementado (resumen)

- Lectura de `erp_fraud_data.zip` y localización de `joint_datasets/`
- Validación de ficheros esperados del dataset
- Carga robusta de CSV/Parquet desde zip a `pandas`
- Normalización de tipos (fechas, importes, IDs) y limpieza técnica mínima
- Conexión DuckDB + carga de tablas (`overwrite` / `append`)
- Métricas por tabla (`rows_loaded`, `duration_ms`)
- Cálculo de `dataset_hash` reproducible
- Generación de `schema_summary.json` y `run_metadata.json`
- Logging estructurado JSONL para ingesta
- Manejo de errores típicos (zip corrupto, CSV mal formado, parseos)

## Cómo verificarlo (actual)

Ejecutar tests unitarios de la base de ingesta/storage:

```bash
pytest -q tests/test_rf01_ingest_storage.py
```

Resultado esperado:

- `9 passed` (puede variar si se amplían tests)

## Notas

- El dataset grande `erp_fraud_data.zip` está trackeado con Git LFS.
- Esta fase construye la infraestructura reproducible; la ejecución de tests de fraude (catálogo/motor) se implementa en requisitos posteriores (`RF03`, `RF04`).
