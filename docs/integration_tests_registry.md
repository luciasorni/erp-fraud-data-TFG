# Registro Unificado — Tests de Integración

Este documento agrupa **solo tests de integración** del proyecto, indicando:

- requisito al que dan cobertura,
- qué validan de forma integrada,
- dónde están implementados,
- en qué documentación se referencian,
- y cómo ejecutarlos.

## Criterio de inclusión

Se consideran aquí tests que validan interacción entre múltiples componentes (nodos, scripts, persistencia, contratos E2E, tooling/config), no tests unitarios puros.

## Cobertura RF14c (07-23)

| Test file | Requisito/subrequisito cubierto | Propósito | Tipo | ¿Mocks/Fakes? |
|---|---|---|---|---|
| `tests/test_rf14c07_env_config.py` | RF14c-07 | Validar defaults/env parsing y validaciones de `RUN_MODE`, `PROCESS_SCOPE`, `LANGSMITH_TRACING` | Unit | No (usa `monkeypatch` de env local) |
| `tests/test_rf14c08_s3_io.py` | RF14c-08 | Verificar parseo S3 URI, upload/download por prefijo y preservación de rutas relativas | Integration (capa IO) | Sí (`FakeS3Client`) |
| `tests/test_rf14c09_artifact_hash.py` | RF14c-09 | Probar reproducibilidad y sensibilidad del `artifact_hash` por contenido/scope/orden estable | Unit/Integration (filesystem local) | No AWS, solo ficheros temporales |
| `tests/test_rf14c09_run_metadata.py` | RF14c-09 | Garantizar persistencia de `artifact_hash` y `process_scope` en `run_metadata.json` | Unit | No |
| `tests/test_rf14c10_state_store.py` | RF14c-10 | Validar rutas por scope y lectura/escritura idempotente de `last_artifact_hash.json` | Integration (state store API) | Sí (`FakeS3Client`, `ClientError` fake) |
| `tests/test_rf14c11_cloud_runner.py` | RF14c-11 | Cubrir dispatcher local/cloud, flujo cloud, subida outputs, state update en éxito y no update en fallo | Integration | Sí (mocks de S3/runner/state) |
| `tests/test_rf14c11_cloud_runner.py::test_rf14c11_cloud_graph_mode_runs_graph_after_deterministic` | RF14c-11 + RF14c grafo cloud | Verificar `--pipeline-mode graph` en cloud: ejecuta base + invoca grafo y mantiene upload/state | Integration | Sí (mocks de runner/grafo/S3/state) |
| `tests/test_rf14c11_cloud_runner.py::test_rf14c11_execute_graph_pipeline_invokes_run_graph_full` | RF14c-11 + RF14 | Verificar integración de `run_graph_full(...)` con `process_family` y persistencia mínima `graph/*` | Integration | Sí (mock de `run_graph_full`) |
| `tests/test_rf14c11_cloud_runner.py::test_rf14c11_cloud_restores_red_flags_mapping_from_scope` | RF14c-20/21 hardening | Verificar restore cloud de `config/red_flags_mapping.yaml` desde `artifacts/mappings/<scope>/` | Integration | Sí (fake download) |
| `tests/test_rf14c11_cloud_runner.py::test_rf14c11_cloud_restores_weights_from_scope` | RF14c-20/21 hardening | Verificar restore cloud de `config/weights.yaml` desde `artifacts/mappings/<scope>/` | Integration | Sí (fake download) |
| `tests/test_rf14c11_cloud_runner.py::test_rf14c11_ensure_report_dictionary_artifacts_creates_run_local_files` | RF14c-12 hardening cloud | Garantizar que artefactos de dictionary del run existen para validación de outputs/report | Unit | No |
| `tests/test_rf14c12_run_outputs.py` | RF14c-12 | Validar outputs obligatorios, opcionales de grafo y metadatos mínimos (incl. `process_scope=both`) | Unit/Integration (contract) | No |
| `tests/test_rf14c23_lambda_trigger.py` | RF14c-23 | Validar lógica Lambda de trigger: filtros de evento, comparación hash y decisión `skip/launch` | Unit/Integration (handler) | Sí (monkeypatch de funciones AWS) |

### Nota sobre cobertura AWS real

- Los tests RF14c en `pytest` **no** hacen integración real contra AWS (cuenta/recursos), por diseño.
- Para AWS real se usan evidencias operativas de ejecución (`docs/cloud/rf14c_20_*.md`, `docs/cloud/rf14c_21_*.md`, `docs/cloud/RF14c_22_*.md`, `docs/cloud/RF14c_23_*.md` y `docs/cloud/evidences/*`).

## Mapa por requisito

| Requisito | Test de integración | Tipo | Qué valida (resumen) | Documentación asociada |
|---|---|---|---|---|
| RF14 | `tests/test_rf14_graph_integration.py` | E2E grafo full | Flujo `ingest -> kb_index -> hypothesis_planner -> test_planner -> executor -> explainer -> scoring -> persist`, estado por nodo `OK`, artefactos persistidos | `docs/rf14.md` (RF14-13, RF14-15), `docs/multiagent_graph_architecture.md` |
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
| RF11 | `tests/test_rf11_o2c_cli_run.py` | E2E O2C run | `run --process-family o2c` con autoload de `raw_data/*.zip` a DuckDB, transform+validación O2C, persistencia de artefactos (`run_metadata`, `schema_summary`, `data_validation_report`, `report`) y fallo controlado por fuentes fail-fast | `docs/o2c/rf11_08_orchestration_process_family.md`, `docs/o2c/rf11_13_o2c_integration_tests.md` |
| RF11 | `tests/test_rf11_o2c_transform.py` + `tests/test_rf11_o2c_validation.py` | Integración datos O2C | Integración `raw -> canónico O2C` en DuckDB y validación técnica de entidades/required fields | `docs/o2c/rf11_05_raw_to_canonical_transform.md`, `docs/o2c/rf11_06_o2c_technical_validation.md` |
| RF11 | `tests/test_rf11_o2c_data_dictionary.py` | Integración artefactos docs | Generación consistente de data dictionary O2C desde schema+mapping | `docs/o2c/rf11_10_o2c_data_dictionary.md` |
| RF11 | `tests/test_rf11_o2c_hypothesis_matrix.py` + `tests/test_rf11_o2c_taxonomy.py` | Integración gobernanza analítica | Consistencia matriz hipótesis->tests->evidencia y alineación de `fraud_type` O2C con Fraud Tree | `docs/o2c/rf11_11_o2c_hypothesis_matrix.md`, `docs/o2c/rf11_12_o2c_fraud_taxonomy.md` |
| RF11 | `tests/test_rf11_o2c_catalog_execution.py` | Integración catálogo O2C ejecutable | Ejecución real de tests de fraude O2C en `TestRunner` contra tablas canónicas O2C (order/delivery/collection/invoice), incluyendo `TST-O2C-INVOICE-AMOUNT-ANOMALY` y `TST-O2C-INVOICE-DATE-SEQUENCE` | `docs/o2c/rf11_15_operational_runbook.md` |
| RF11 | `tests/test_rf11_o2c_graph_integration.py` | E2E grafo O2C | `run_graph_full` con nodos/agents, `process_family=o2c`, catálogo O2C y persistencia en grafo | `docs/o2c/rf11_13_o2c_integration_tests.md`, `docs/o2c/rf11_15_operational_runbook.md` |
| RF16 | `tests/test_rf16_runs_comparison.py` | Integración storage comparación de runs | Carga snapshots desde artefactos persistidos, comparación cross-process/single-run, selección de latest por familia | `docs/rf16.md` |
| RF16 | `tests/test_rf16_cli_compare_runs.py` | Integración CLI RF16 | Comandos `list-runs` y `compare-runs`, con generación de `rf16_second_level_analysis.json/md` | `docs/rf16.md`, `docs/how_to_run.md` |
| RF16 | `tests/test_rf16_second_level_agent_node.py` | Integración nodo/agente RF16 | Ejecución de `second_level_explainer` como último nodo del grafo, persistiendo `graph/second_level_analysis.json|md` | `docs/rf16.md`, `docs/multiagent_graph_architecture.md` |
| RF20 | `tests/test_rf20_api.py` | Integración API | Contrato HTTP base `/api/v1`, validación de payloads, `scope=both`, shape UI de `/graph` y rechazo de acciones inseguras en drilldown | `docs/rf20.md`, `README.md` |
| RF20 | `tests/test_rf20_services.py` | Integración services | Orquestación de dos runs para `both` y adaptación de artefactos `graph/*` a respuestas legibles para UI | `docs/rf20.md` |
| RF20 | `tests/test_rf20_ui_api_client.py` | Integración cliente UI | Centralización de llamadas HTTP de Streamlit sobre `/api/v1` y manejo básico de errores | `docs/rf20.md`, `README.md` |
| RF20 | `tests/test_rf20_ui_utils.py` | Unit/Integration UI | Formateadores y mapeos visuales para métricas, estados y hallazgos de la interfaz Streamlit | `docs/rf20.md` |

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

### RF16 (comparación de runs)

```bash
python3 -m pytest -q \
  tests/test_rf16_runs_comparison.py \
  tests/test_rf16_cli_compare_runs.py \
  tests/test_rf16_second_level_agent_node.py
```

### RF20 (API de aplicación)

```bash
python3 -m pytest -q \
  tests/test_rf20_api.py \
  tests/test_rf20_services.py \
  tests/test_rf20_ui_api_client.py \
  tests/test_rf20_ui_utils.py
```

## Evidencia documental por bloque

- RF14: `docs/rf14.md`
- RF14b: `docs/rf14b.md`, `docs/rf14b_verification.md`
- RF15c: `docs/rf15c.md`, `docs/rf15c_verification.md`
- RF18: `docs/scoring.md`, `docs/rf18_verification.md`
- RF11/O2C: `docs/o2c/README.md`, `docs/o2c/rf11_13_o2c_integration_tests.md`
- RF16: `docs/rf16.md`
- RF20: `docs/rf20.md`
- Operación de ejecución: `docs/how_to_run.md`

## Nota de trazabilidad

Además de `pytest`, la evidencia operativa real se conserva en:

- `run_results/<run_id>/graph/*`
- `run_results/<run_id>/report.*`
- `run_results/pre_langsmith_gate.json` (cuando aplica gate RF14b)
