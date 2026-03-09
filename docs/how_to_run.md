# Cómo Ejecutar (Local)

## Pre-requisitos

- Python del entorno local (en este proyecto se está usando Anaconda para tests)
- Dataset `erp_fraud_data.zip` disponible en raíz del repo
- Git LFS instalado para clonar correctamente el zip trackeado

## Comandos útiles

Validar diccionario:

```bash
python3 -m src.erp_fraud.cli.main validate-dictionary \
  --dictionary data_dictionary.json \
  --catalog tests/catalog \
  --output-json
```

Ejecutar tests RF01:

```bash
/opt/anaconda3/bin/python -m pytest -q tests/test_rf01_ingest_storage.py
```

Ejecutar tests RF02:

```bash
/opt/anaconda3/bin/python -m pytest -q tests/test_rf02_data_dictionary.py
```

Ejecutar tests RF02b:

```bash
/opt/anaconda3/bin/python -m pytest -q tests/test_rf02b_data_validation.py
```

Ejecutar tests RF03:

```bash
/opt/anaconda3/bin/python -m pytest -q tests/test_rf03_catalog.py
```

Ejecutar tests RF04:

```bash
/opt/anaconda3/bin/python -m pytest -q tests/test_rf04_runner.py
```

Ejecutar tests RF05:

```bash
/opt/anaconda3/bin/python -m pytest -q tests/test_rf05_result_schema_and_writer.py
```

## Validación técnica (RF02b)

Si ya tienes columnas requeridas por test, el pipeline genera:

- `data_validation_report.json`
- sección `Data Validation` en `report.md` (enlazando el JSON)

Regla operativa:

- si hay fallos críticos -> bloquear ejecución de tests
- si hay solo warnings -> continuar ejecución

## Catálogo RF03

- Especificaciones en `tests/catalog/` (YAML versionado por test)
- Changelog en `tests/CHANGELOG.md`
- Referencias SQL en `sql/tests/`

Implementaciones actuales:

- `TST-DUPLICATE-POSTINGS`
- `TST-UNUSUAL-AMOUNT-BY-VENDOR`

## Runner seguro RF04

- Ejecución solo de tests en allowlist (`tests/catalog`)
- Timeout por test (best-effort) opcional
- Continuidad si un test falla (`ERROR`) o expira (`TIMEOUT`)
- Persistencia de:
  - `test_runs.json`
  - `test_runner_logs.jsonl`

## Outputs RF05

- `ResultSchema` validado por test
- `entity_key` estable (`key=value|key2=value2`)
- Serialización por test en:
  - `tests_outputs/<test_id>/findings.jsonl`
  - `tests_outputs/<test_id>/findings.parquet` (opcional)
  - `tests_outputs/<test_id>/sample_top20.json`

## Drilldown RF06

1. Localiza un `entity_key` en un output por test:

```bash
cat run_results/<run_id>/tests_outputs/TST-UNUSUAL-AMOUNT-BY-VENDOR/findings.jsonl
```

2. Ejecuta drilldown seguro:

```bash
python3 -m src.erp_fraud.cli.main drilldown \
  --run-id <run_id> \
  --test-id TST-UNUSUAL-AMOUNT-BY-VENDOR \
  --entity-key "betrag=10296.0|kreditor=V1024"
```

3. Guardar salida en fichero:

```bash
python3 -m src.erp_fraud.cli.main drilldown \
  --run-id <run_id> \
  --test-id TST-UNUSUAL-AMOUNT-BY-VENDOR \
  --entity-key "betrag=10296.0|kreditor=V1024" \
  --output run_results/<run_id>/drilldowns/example_unusual_amount.json
```

Notas:

- Sin SQL libre: solo plantillas allowlist.
- Si faltan keys mínimas o hay filtros no permitidos, devuelve error controlado.
- `limit_rows` máximo: `200`.

## Evidencias

- Artefactos de ejecución en `run_results/<run_id>/`
- DB local generada en `erp.duckdb`
- Ejecución de tests: `run_results/<run_id>/test_runs.json`
- Logs por test: `run_results/<run_id>/test_runner_logs.jsonl`
