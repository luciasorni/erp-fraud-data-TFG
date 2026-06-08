# Datos

Este documento resume el estado vigente del tratamiento de datos. La versión histórica de fase 1 se conserva en `docs/legacy/data_phase1.md`.

## Dataset de entrada

El proyecto trabaja con un ZIP ERP controlado, normalmente `erp_fraud_data.zip`, y lo procesa mediante el CLI o mediante la API/UI cuando el dataset se registra en S3.

## Familias de proceso

| Familia | Base de datos lógica | Configuración / rutas relevantes |
|---|---|---|
| P2P | Tabla analítica `fraud_1` y datasets agregados P2P. | `tests/catalog`, `sql/tests/tst_*`, `data_dictionary.json`. |
| O2C | Modelo canónico O2C en DuckDB. | `config/canonical_schema_o2c.yaml`, `config/column_mapping_o2c.yaml`, `config/o2c_entity_identity.yaml`, `tests/catalog_o2c`. |

## Artefactos de datos por run

Los artefactos principales se escriben en `run_results/<run_id>/` en ejecución local y en `runs/<run_id>/` en S3 para cloud.

- `run_metadata.json`
- `schema_summary.json`
- `data_validation_report.json`
- `ingest_logs.jsonl`
- `test_runner_logs.jsonl`
- `test_runs.json`
- `ranking.json`
- `report.json`

En modo graph se añaden artefactos bajo `graph/`.

## Validación técnica

La validación previa comprueba columnas requeridas por catálogo, parseo de fechas/importes, nulos y rangos básicos. Los errores críticos bloquean el run; los warnings quedan registrados y permiten continuar.

## O2C

O2C no reutiliza sin más la tabla P2P. Añade transformación desde raw a tablas canónicas, mapping de columnas, validación específica y catálogo propio. La documentación detallada está en `docs/o2c/`.

## Limitaciones

- La calidad y cobertura dependen de que las tablas y columnas requeridas existan.
- El modelo O2C cubre el alcance definido del TFG; no pretende representar todo ERP posible.
- La KB local puede usar fuentes documentales, pero no sustituye el contrato de datos ni el catálogo ejecutable.
