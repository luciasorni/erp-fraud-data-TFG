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

## Cómo verificarlo (actual)

Ejecutar tests unitarios de la base de ingesta/storage:

```bash
/opt/anaconda3/bin/python -m pytest -q tests/test_rf01_ingest_storage.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf02_data_dictionary.py
```

Resultado esperado:

- RF01: `9 passed` (puede variar si se amplían tests)
- RF02: `6 passed` (puede variar si se amplían tests)

## Notas

- El dataset grande `erp_fraud_data.zip` está trackeado con Git LFS.
- Esta fase construye la infraestructura reproducible; la ejecución de tests de fraude (catálogo/motor) se implementa en requisitos posteriores (`RF03`, `RF04`).
