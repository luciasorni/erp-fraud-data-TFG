# RF11-14 — Regresión cruzada P2P vs O2C

## 1) Objetivo

Verificar que la introducción de O2C no rompe el flujo existente P2P.

RF11-14 se valida ejecutando en el mismo punto:

1. subset de smoke tests P2P,
2. subset de smoke tests O2C.

## 2) Script de verificación

- `scripts/run_rf11_cross_regression.py`

Genera evidencia:

- `run_results/<run_id>/rf11_14_cross_regression.json`

## 3) Ejecución

```bash
python3 scripts/run_rf11_cross_regression.py \
  --run-id rf11-14-cross-check
```

## 4) Checks incluidos

- `p2p_smoke_subset`
  - `tests/test_rf01_ingest_storage.py`
  - `tests/test_rf13_catalog_selection.py`
  - `tests/test_rf14_graph_structure.py`
- `o2c_smoke_subset`
  - `tests/test_rf11_o2c_cli_run.py`
  - `tests/test_rf11_o2c_transform.py`
  - `tests/test_rf11_o2c_validation.py`
  - `tests/test_rf11_o2c_data_dictionary.py`
  - `tests/test_rf11_o2c_hypothesis_matrix.py`
  - `tests/test_rf11_o2c_taxonomy.py`

## 5) Criterio de aceptación RF11-14

- `overall_status=OK` en `rf11_14_cross_regression.json`,
- ambos checks (`p2p_smoke_subset`, `o2c_smoke_subset`) en `OK`.
