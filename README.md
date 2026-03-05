# erp-fraud-data-TFG

Base del TFG para detección de fraude en ERP (fase inicial P2P) usando el dataset `ERP Fraud Data` y DuckDB.

## Documentación

- `docs/architecture.md`
- `docs/rf01.md`
- `docs/rf02.md`
- `docs/rf03.md`
- `docs/rf04.md`
- `docs/data.md`
- `docs/how_to_run.md`

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

## Data Dictionary (RF02)

Se añadió una base de diccionario de datos para alinear tests y campos del dataset.

Artefactos:

- `data_dictionary.json`: formato máquina
- `data_dictionary.md`: formato humano

Capacidades actuales:

- Generar borrador desde `schema_summary.json` (tablas/columnas/tipos)
- Garantizar campos mínimos por entrada:
  - `table`, `column`, `type`, `description`, `examples`, `used_in_tests`
- Anotar `used_in_tests` desde catálogo de tests (`tests/catalog`)
- Validar completitud: falla si un test usa un campo no documentado

CLI disponible:

```bash
python3 -m src.erp_fraud.cli.main validate-dictionary \
  --dictionary data_dictionary.json \
  --catalog tests/catalog
```

Opcional:

- `--output-json` para resumen en JSON

Código de salida:

- `0`: diccionario completo
- `1`: faltan campos documentados usados por tests
- `2`: error de entrada/parseo

## Data Validation (RF02b)

Se añadió validación técnica previa a ejecución de tests, basada en columnas requeridas por `TestSpec`.

Checks implementados:

- `missing_required_columns` (critical)
- `type_parse_errors_dates` (critical)
- `type_parse_errors_amounts` (critical)
- `null_percentage_required_columns` (warning)
- `basic_ranges_dates` (warning)
- `basic_ranges_amounts` (warning)

Artefacto principal:

- `data_validation_report.json` (estructura estable, ordenada y con severidades)

Regla de bloqueo:

- el run se bloquea **solo** si hay errores `critical`
- si hay solo `warning`, el run continúa

## Fraud Test Catalog (RF03)

Se añadió un catálogo inicial versionado de tests antifraude (alineado con ACFE/COSO) con 2 controles P2P implementados.

Catálogo:

- `tests/catalog/tst_duplicate_postings.yaml`
- `tests/catalog/tst_unusual_amount_by_vendor.yaml`

Componentes:

- Esquema `TestSpec`: `src/erp_fraud/catalog/test_spec_schema.py`
- Loader y validación de `TestSpec`: `src/erp_fraud/catalog/test_spec_loader.py`
- Ejecución de tests y resultado estándar: `src/erp_fraud/catalog/test_execution.py`
- SQL de referencia: `sql/tests/`
- Changelog de catálogo: `tests/CHANGELOG.md`

Nota:

- `data_requirements.required_columns_exact` define columnas exactas por test para soporte de validación técnica previa (RF02b).

## Secure Test Runner (RF04)

Se añadió el motor de ejecución seguro base para catálogo:

- Allowlist de `test_id` (solo IDs existentes en `tests/catalog`)
- Continuidad ante fallo por test (`status=ERROR` + `error_summary`)
- Timeout por test best-effort (`status=TIMEOUT`)
- Métricas de tiempo:
  - por test
  - por fase (`selection`, `execution`, `total`)
- Persistencia de resultados de ejecución:
  - `test_runs.json` por run
- Logs por test:
  - `test_start` / `test_end` en JSONL con `run_id` y `test_id`

Componente principal:

- `src/erp_fraud/catalog/test_runner.py`

## Cómo verificarlo (actual)

Ejecutar tests unitarios de la base de ingesta/storage:

```bash
/opt/anaconda3/bin/python -m pytest -q tests/test_rf01_ingest_storage.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf02_data_dictionary.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf02b_data_validation.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf03_catalog.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf04_runner.py
```

Resultado esperado:

- RF01: `9 passed` (puede variar si se amplían tests)
- RF02: `6 passed` (puede variar si se amplían tests)
- RF02b: `4 passed` (puede variar si se amplían tests)
- RF03: `4 passed` (puede variar si se amplían tests)
- RF04: `6 passed` (puede variar si se amplían tests)

## Notas

- El dataset grande `erp_fraud_data.zip` está trackeado con Git LFS.
- La ejecución inicial de tests de catálogo está implementada en RF03; el motor de ejecución completo y endurecido se extiende en `RF04`.
