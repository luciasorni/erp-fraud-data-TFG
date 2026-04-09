# Registro Unificado — Tests de Integración

Este documento agrupa **solo tests de integración** del proyecto, indicando:

- requisito al que dan cobertura,
- qué validan de forma integrada,
- dónde están implementados,
- en qué documentación se referencian,
- y cómo ejecutarlos.

## Criterio de inclusión

Se consideran aquí tests que validan interacción entre múltiples componentes (nodos, scripts, persistencia, contratos E2E, tooling/config), no tests unitarios puros.

## Mapa por requisito

| Requisito | Test de integración | Tipo | Qué valida (resumen) | Documentación asociada |
|---|---|---|---|---|
| RF14 | `tests/test_rf14_graph_integration.py` | E2E grafo full | Flujo `ingest -> kb_index -> hypothesis_planner -> test_planner -> executor -> explainer -> scoring -> persist`, estado por nodo `OK`, artefactos persistidos | `docs/rf14.md` (RF14-13, RF14-15), `docs/langgraph_architecture.md` |
| RF14 | `tests/test_rf14_graph_routing.py` | Integración de orquestación | Routing condicional, retries/timeouts, abort controlado + persist en abort | `docs/rf14.md` |
| RF14b | `tests/test_rf14b_contracts.py` | Integración contratos + backward-compat | Compatibilidad de contratos/salidas entre piezas del pipeline | `docs/rf14b.md`, `docs/rf14b_verification.md` |
| RF14b | `tests/test_rf14b_env_validation.py` | Integración runtime/env | Validación de variables de entorno y perfiles antes de tracing cloud | `docs/rf14b.md`, `docs/pre_langsmith_checklist.md` |
| RF14b | `tests/test_rf14b_evaluators.py` | Integración evaluadores | Evaluación automática de coherencia entre findings/explanations/scores | `docs/rf14b.md`, `docs/rf14b_verification.md` |
| RF14b | `tests/test_rf14b_langsmith_dataset.py` | Integración dataset LangSmith | Generación/publicación (o modo local) de dataset de evaluación | `docs/rf14b.md`, `docs/langsmith_experiments.md` |
| RF14b | `tests/test_rf14b_experiments_script.py` | Integración script de experimentos | Ejecución de `run_rf14b_experiments.py` y estructura de outputs | `docs/rf14b.md`, `docs/rf14b_verification.md` |
| RF15c | `tests/test_rf15c_multiagent_integration.py` | Integración multiagente | Flujo multiagente con stubs LLM/KB/runner, consistencia de outputs y persistencia final | `docs/rf15c.md` (RF15c-13), `docs/rf15c_verification.md` |
| RF15c | `tests/test_rf15c_end_to_end_contract.py` | E2E contractual | Coherencia contractual de outputs E2E (`selected_tests`, `findings`, `explanations`, `scores`, probs~1.0) | `docs/rf15c.md` (RF15c-16), `docs/rf15c_verification.md` |
| RF15c | `tests/test_rf15c_manual_e2e_script.py` | Integración script manual E2E | Construcción de evidencia RF15c-14 (`rf15c_14_manual_evidence.json`) | `docs/rf15c.md` (RF15c-14), `docs/how_to_run.md` |
| RF18 | `tests/test_rf18_scoring_end_to_end.py` | E2E scoring + persist | Pipeline scoring completo (incl. compare/experiment) y artefactos `scores.json`, `score_compare.json`, `score_experiment.json` | `docs/scoring.md`, `docs/rf18_verification.md` |
| RF13 | `tests/test_rf13_p2_additional_catalog.py` | Integración catálogo P2P (segunda ola) | Ejecución real de tests P2P adicionales (`TST-UNUSUAL-POSTING-TIMES`, `TST-LARGE-EVEN-DOLLAR-ENTRIES`) con `TestRunner` y salida estándar | `docs/rf13.md`, `docs/how_to_run.md` |
| RF13 | `tests/test_rf13_p2p_hypothesis_matrix.py` | Integración gobernanza P2P | Consistencia de matriz P2P `hipótesis -> tests -> evidencias -> keys` con catálogo y drilldown | `docs/p2p/rf13_p2p_hypothesis_matrix.md` |
| RF11 | `tests/test_rf11_o2c_cli_run.py` | E2E O2C run | `run --process-family o2c` con transform+validación O2C, persistencia de artefactos (`run_metadata`, `schema_summary`, `data_validation_report`, `report`) y fallo controlado por fuentes fail-fast | `docs/o2c/rf11_08_orchestration_process_family.md`, `docs/o2c/rf11_13_o2c_integration_tests.md` |
| RF11 | `tests/test_rf11_o2c_transform.py` + `tests/test_rf11_o2c_validation.py` | Integración datos O2C | Integración `raw -> canónico O2C` en DuckDB y validación técnica de entidades/required fields | `docs/o2c/rf11_05_raw_to_canonical_transform.md`, `docs/o2c/rf11_06_o2c_technical_validation.md` |
| RF11 | `tests/test_rf11_o2c_data_dictionary.py` | Integración artefactos docs | Generación consistente de data dictionary O2C desde schema+mapping | `docs/o2c/rf11_10_o2c_data_dictionary.md` |
| RF11 | `tests/test_rf11_o2c_hypothesis_matrix.py` + `tests/test_rf11_o2c_taxonomy.py` | Integración gobernanza analítica | Consistencia matriz hipótesis->tests->evidencia y alineación de `fraud_type` O2C con Fraud Tree | `docs/o2c/rf11_11_o2c_hypothesis_matrix.md`, `docs/o2c/rf11_12_o2c_fraud_taxonomy.md` |
| RF11 | `tests/test_rf11_o2c_catalog_execution.py` | Integración catálogo O2C ejecutable | Ejecución real de tests de fraude O2C en `TestRunner` contra tablas canónicas O2C | `docs/o2c/rf11_15_operational_runbook.md` |
| RF11 | `tests/test_rf11_o2c_graph_integration.py` | E2E grafo O2C | `run_graph_full` con nodos/agents, `process_family=o2c`, catálogo O2C y persistencia en grafo | `docs/o2c/rf11_13_o2c_integration_tests.md`, `docs/o2c/rf11_15_operational_runbook.md` |

## Suites de ejecución recomendadas

### RF14 (grafo)

```bash
python3 -m pytest -q \
  tests/test_rf14_graph_routing.py \
  tests/test_rf14_graph_integration.py
```

### RF14b (pre-LangSmith)

```bash
python3 -m pytest -q \
  tests/test_rf14b_contracts.py \
  tests/test_rf14b_env_validation.py \
  tests/test_rf14b_evaluators.py \
  tests/test_rf14b_langsmith_dataset.py \
  tests/test_rf14b_experiments_script.py
```

### RF15c (multiagente E2E)

```bash
python3 -m pytest -q \
  tests/test_rf15c_multiagent_integration.py \
  tests/test_rf15c_end_to_end_contract.py \
  tests/test_rf15c_manual_e2e_script.py
```

### RF18 (scoring E2E)

```bash
python3 -m pytest -q tests/test_rf18_scoring_end_to_end.py
```

### RF11 (O2C integración)

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

### RF13 (P2P segunda ola)

```bash
python3 -m pytest -q \
  tests/test_rf13_p2_additional_catalog.py \
  tests/test_rf13_p2p_hypothesis_matrix.py
```

## Evidencia documental por bloque

- RF14: `docs/rf14.md`
- RF14b: `docs/rf14b.md`, `docs/rf14b_verification.md`
- RF15c: `docs/rf15c.md`, `docs/rf15c_verification.md`
- RF18: `docs/scoring.md`, `docs/rf18_verification.md`
- RF11/O2C: `docs/o2c/README.md`, `docs/o2c/rf11_13_o2c_integration_tests.md`
- Operación de ejecución: `docs/how_to_run.md`

## Nota de trazabilidad

Además de `pytest`, la evidencia operativa real se conserva en:

- `run_results/<run_id>/graph/*`
- `run_results/<run_id>/report.*`
- `run_results/pre_langsmith_gate.json` (cuando aplica gate RF14b)
