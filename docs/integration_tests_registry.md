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

## Evidencia documental por bloque

- RF14: `docs/rf14.md`
- RF14b: `docs/rf14b.md`, `docs/rf14b_verification.md`
- RF15c: `docs/rf15c.md`, `docs/rf15c_verification.md`
- RF18: `docs/scoring.md`, `docs/rf18_verification.md`
- Operación de ejecución: `docs/how_to_run.md`

## Nota de trazabilidad

Además de `pytest`, la evidencia operativa real se conserva en:

- `run_results/<run_id>/graph/*`
- `run_results/<run_id>/report.*`
- `run_results/pre_langsmith_gate.json` (cuando aplica gate RF14b)

