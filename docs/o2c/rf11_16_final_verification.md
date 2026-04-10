# RF11-16 — Verificación final y evidencias

## 1) Estado de cierre RF11

Cobertura implementada:

- RF11-01 .. RF11-14: implementado y documentado.
- RF11-15: runbook operativo O2C (CLI + grafo/agents + llm real).
- RF11-16: este cierre de verificación/evidencias.

## 2) Evidencias mínimas

- Run determinista O2C:
  - `run_results/rf11-o2c-cli/`
- Validación matriz hipótesis O2C:
  - `run_results/rf11-11-check-local-2/rf11_11_o2c_hypothesis_matrix_validation.json`
- Validación taxonomía O2C:
  - `run_results/rf11-12-check-local-2/rf11_12_o2c_taxonomy_validation.json`
- Regresión cruzada P2P vs O2C:
  - `run_results/rf11-14-check-local/rf11_14_cross_regression.json`

## 3) Suite de verificación recomendada

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

## 4) Riesgos abiertos (controlados)

1. Catálogo O2C actual es baseline operativo (7 tests); cobertura funcional ampliable por iteraciones.
2. En rama O2C de CLI, el reporte se genera con `test_runs=[]` y `ranking.rows=[]` por diseño actual de RF11 (la ejecución de tests O2C se hace en grafo/agents con catálogo O2C).
3. Calidad de detección depende de calidad y completitud de tablas SAP raw disponibles por dataset.

## 5) Criterio final de aceptación RF11

Se considera RF11 aceptado cuando:

1. O2C canónico se construye y valida (`process_family=o2c`),
2. grafo/agents ejecuta catálogo O2C con `llm_mode=stub|real`,
3. taxonomía O2C está alineada con Fraud Tree,
4. regresión P2P vs O2C está en verde,
5. documentación operativa/integración queda consolidada.
