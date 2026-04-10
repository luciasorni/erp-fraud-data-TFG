# RF11-13 — Tests de integración O2C (E2E + persistencia + reporte)

## 1) Objetivo

Garantizar que una ejecución O2C completa:

1. transforma y valida datos canónicos O2C,
2. persiste artefactos estándar de run,
3. genera reporte final sin romper compatibilidad P2P.

Además, garantizar que el flujo O2C no rompe compatibilidad transversal con P2P.

## 2) Suite de integración O2C usada

- `tests/test_rf11_o2c_cli_run.py`
  - `test_rf11_08_cli_run_o2c_mode_generates_artifacts`
  - `test_rf11_08_cli_run_o2c_mode_fails_when_missing_fail_fast_sources`
- `tests/test_rf11_o2c_transform.py`
- `tests/test_rf11_o2c_validation.py`
- `tests/test_rf11_o2c_data_dictionary.py`
- `tests/test_rf11_o2c_hypothesis_matrix.py`
- `tests/test_rf11_o2c_taxonomy.py`
- `tests/test_rf11_o2c_catalog_execution.py`
- `tests/test_rf11_o2c_graph_integration.py`

## 3) Qué se verifica (integración)

En E2E O2C (`run --process-family o2c`) se verifica:

- creación de artefactos:
  - `run_metadata.json`
  - `schema_summary.json`
  - `data_validation_report.json`
  - `report.json`
  - `report.md`
- contenido coherente de `report.json` para rama O2C:
  - `summary.tests_total=0`
  - `summary.ranking_entities=0`
  - `test_runs=[]`
  - `ranking.rows=[]`
- consistencia de `run_id` y `process_family=o2c`,
- reporte con `overall_status=OK` cuando fuentes mínimas existen,
- fallo controlado cuando falta tabla `fail-fast` (ej. `VBAK` para `o2c_order`).

## 4) Ejecución recomendada

```bash
python3 -m pytest -q \
  tests/test_rf11_o2c_cli_run.py \
  tests/test_rf11_o2c_transform.py \
  tests/test_rf11_o2c_validation.py \
  tests/test_rf11_o2c_data_dictionary.py \
  tests/test_rf11_o2c_hypothesis_matrix.py \
  tests/test_rf11_o2c_taxonomy.py \
  tests/test_rf11_o2c_catalog_execution.py \
  tests/test_rf11_o2c_graph_integration.py
```

## 5) Criterio de aceptación RF11-13

- suite anterior en verde,
- evidencia de run O2C local con artefactos completos en `run_results/`,
- sin regresiones funcionales en flujo base P2P (a cubrir en RF11-14).
