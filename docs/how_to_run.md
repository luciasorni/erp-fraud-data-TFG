# Cómo Ejecutar (Local)

## Pre-requisitos

- Python del entorno local (en este proyecto se está usando Anaconda para tests)
- Dataset `erp_fraud_data.zip` disponible en raíz del repo
- Git LFS instalado para clonar correctamente el zip trackeado

## Comandos útiles

Registro unificado de tests de integración:

- `docs/integration_tests_registry.md`

Ejecución end-to-end (RF10):

```bash
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip
```

Atajo con Make:

```bash
make run INPUT_ZIP=erp_fraud_data.zip
```

Variantes frecuentes:

```bash
# Carpeta de salidas personalizada + run_id explícito
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --out-dir run_results \
  --run-id rf10-demo

# Ejecutar subset de tests + top-k override
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --select-tests TST-DUPLICATE-POSTINGS,TST-UNUSUAL-AMOUNT-BY-VENDOR,TST-UNUSUAL-POSTING-TIMES,TST-LARGE-EVEN-DOLLAR-ENTRIES \
  --top-k 20

# Validar matriz de hipótesis P2P (gobernanza planner/explainer)
python3 scripts/run_rf13_p2p_hypothesis_matrix.py \
  --run-id rf13-p2p-matrix-check

# Ejecutar subset por fraud_type/tags (RF13-05)
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --select-fraud-types duplicate_payment,amount_anomaly \
  --select-tags p2p,acfe

# Declarar familia de proceso en metadata/config (RF11-07)
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --process-family p2p

# Ejecutar rama O2C (requiere tablas raw SAP ya cargadas en DuckDB main)
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --db-path erp.duckdb \
  --process-family o2c \
  --o2c-canonical-schema-config config/canonical_schema_o2c.yaml \
  --o2c-identity-config config/o2c_entity_identity.yaml \
  --o2c-mapping-config config/column_mapping_o2c.yaml \
  --o2c-target-schema o2c

# Parametrizar por fichero config (json/yaml)
python3 -m src.erp_fraud.cli.main run \
  --config config/run_config.yaml

# Ejecutar run sin rebuild de KB (RF15e)
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --no-kb-index

# Ejecutar run con configs KB explícitas
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --kb-index-enabled \
  --kb-sources-config config/kb_sources.yaml \
  --kb-chunking-config config/kb_chunking.yaml \
  --kb-chroma-config config/kb_chroma.yaml

# RF16: listar runs persistidos
python3 -m src.erp_fraud.cli.main list-runs \
  --base-dir run_results

# RF16: comparar runs concretos (P2P/O2C o cualquier combinación)
python3 -m src.erp_fraud.cli.main compare-runs \
  p2p-real-check-01 o2c-real-fix-01 \
  --base-dir run_results \
  --analysis-id rf16-compare-demo

# RF16: comparar automáticamente último run P2P + último O2C
python3 -m src.erp_fraud.cli.main compare-runs \
  --base-dir run_results \
  --auto-latest-p2p-o2c \
  --analysis-id rf16-latest-demo
```

Calidad rápida:

```bash
make test
make test-rf08
make pre-langsmith-gate
```

Validación de variables por perfil:

```bash
python3 scripts/validate_required_env.py --profile pre_langsmith
python3 scripts/validate_required_env.py --profile langsmith
```

## Run real mínimo (check rápido pre-cloud)

1) Cargar variables del `.env`:

```bash
set -a; source .env; set +a
```

2) Ejecutar run real:

```bash
python3 scripts/run_rf15c_e2e_manual.py \
  --run-id real-check-$(date +%Y%m%d-%H%M%S) \
  --schema-summary-path run_results/rf10-08-acceptance-run/schema_summary.json \
  --catalog-path tests/catalog \
  --persist-base-dir run_results \
  --llm-mode real \
  --rf16-auto-latest-p2p-o2c
```

3) Ver resumen funcional:

```bash
python3 scripts/show_run_summary.py --run-id <run_id>
```

4) Validar metadata crítica:

```bash
python3 - <<'PY'
import json
run_id = "<run_id>"
p = f"run_results/{run_id}/graph/graph_state.json"
m = json.load(open(p))["run_metadata"]
print("graph_status:", m.get("graph_status"))
print("llm_mode:", m.get("llm_mode"))
print("llm_runtime_by_node:", m.get("llm_runtime_by_node"))
print("langsmith_runs:", m.get("langsmith_runs"))
print("langsmith_trace_link:", m.get("langsmith_trace_link"))
PY
```

Resultado esperado mínimo:

- `graph_status=OK`
- `llm_mode=real`
- nodos LLM con `status=OK` en `llm_runtime_by_node`
- `langsmith_runs.status=OK` y `langsmith_trace_link` no vacío (si LangSmith está activo).
- artefactos RF16 de segundo nivel generados:
  - `run_results/<run_id>/graph/second_level_analysis.json`
  - `run_results/<run_id>/graph/second_level_analysis.md`

## Entorno limpio (RF10-06)

Prueba recomendada en máquina con red:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m src.erp_fraud.cli.main run --help
make test-rf08 PYTHON=./.venv/bin/python
```

Pitfalls observados en esta ejecución:

- `ModuleNotFoundError: duckdb` en venv limpio sin dependencias.
- sin conectividad de red, `pip install` no puede descargar paquetes desde PyPI.

Mitigación local:

- usar el entorno del proyecto ya preparado:
  - `python3 -m src.erp_fraud.cli.main run --help`
  - `make test-rf08`

Validar diccionario:

```bash
python3 -m src.erp_fraud.cli.main validate-dictionary \
  --dictionary data_dictionary.json \
  --catalog tests/catalog \
  --output-json
```

Ejecutar tests RF01:

```bash
python3 -m pytest -q tests/test_rf01_ingest_storage.py
```

Ejecutar tests RF02:

```bash
python3 -m pytest -q tests/test_rf02_data_dictionary.py
```

Ejecutar tests RF02b:

```bash
python3 -m pytest -q tests/test_rf02b_data_validation.py
```

Ejecutar tests RF03:

```bash
python3 -m pytest -q tests/test_rf03_catalog.py
```

Ejecutar tests RF04:

```bash
python3 -m pytest -q tests/test_rf04_runner.py
```

Ejecutar tests RF05:

```bash
python3 -m pytest -q tests/test_rf05_result_schema_and_writer.py
```

Ejecutar tests RF06:

```bash
python3 -m pytest -q tests/test_rf06_drilldown.py tests/test_rf06_drilldown_components.py
```

Ejecutar tests RF07:

```bash
python3 -m pytest -q tests/test_rf07_ranking.py
```

Ejecutar tests RF08:

```bash
python3 -m pytest -q tests/test_rf08_reporting.py
```

Ejecutar tests RF13 (catálogo ampliado):

```bash
python3 -m pytest -q \
  tests/test_rf13_catalog_selection.py \
  tests/test_rf13_families.py \
  tests/test_rf13_catalog_validation.py
```

Ejecutar tests RF15b (tools + policies + guardrails):

```bash
python3 -m pytest -q \
  tests/test_rf15b_tools.py \
  tests/test_rf15b_policy_and_schema_guard.py \
  tests/test_rf15b_tool_call_logging.py
```

Ejecutar verificación RF14 (grafo):

```bash
python3 -m pytest -q \
  tests/test_rf14_graph_state.py \
  tests/test_rf14_graph_structure.py \
  tests/test_rf14_ingest_node.py \
  tests/test_rf14_kb_index_node.py \
  tests/test_rf14_hypothesis_planner_node.py \
  tests/test_rf14_test_planner_node.py \
  tests/test_rf14_executor_node.py \
  tests/test_rf14_explainer_node.py \
  tests/test_rf14_scoring_node.py \
  tests/test_rf14_persist_node.py \
  tests/test_rf14_graph_routing.py \
  tests/test_rf14_graph_integration.py
```

Ejecutar verificación AG03 (AlphaCodium loop + artefactos + snapshots):

```bash
python3 -m pytest -q \
  tests/test_ag03_alpha_loop_integration.py \
  tests/test_ag03_alpha_artifacts.py \
  tests/test_ag03_prompt_snapshots.py
```

Ejecutar RF15c-14 manual (E2E + evidencia tutor):

```bash
python3 scripts/run_rf15c_e2e_manual.py \
  --run-id rf15c14-demo \
  --schema-summary-path schema_summary.json \
  --catalog-path tests/catalog \
  --persist-base-dir run_results \
  --llm-mode stub
```

Ejecutar RF15c con proveedor real OpenAI (nodos planner/explainer):

```bash
export OPENAI_API_KEY="<tu_api_key>"
python3 scripts/run_rf15c_e2e_manual.py \
  --run-id rf15c14-real \
  --schema-summary-path schema_summary.json \
  --catalog-path tests/catalog \
  --persist-base-dir run_results \
  --llm-mode real
```

Ejecutar RF11 O2C con LangGraph + agentes (stub/real):

```bash
# 1) construir tablas canónicas O2C en DuckDB
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --db-path erp.duckdb \
  --process-family o2c \
  --o2c-canonical-schema-config config/canonical_schema_o2c.yaml \
  --o2c-identity-config config/o2c_entity_identity.yaml \
  --o2c-mapping-config config/column_mapping_o2c.yaml \
  --o2c-target-schema o2c \
  --run-id rf11-o2c-cli

# 2) ejecutar grafo O2C con catálogo O2C (cambiar llm-mode a stub si quieres coste 0)
python3 scripts/run_rf15c_e2e_manual.py \
  --run-id rf11-o2c-graph-real \
  --schema-summary-path run_results/rf11-o2c-cli/schema_summary.json \
  --catalog-path tests/catalog_o2c \
  --persist-base-dir run_results \
  --process-family o2c \
  --db-path erp.duckdb \
  --schema-name o2c \
  --table-name o2c_order \
  --hypothesis-max-items 4 \
  --test-planner-top-n 4 \
  --test-planner-min-per-hypothesis-real 1 \
  --llm-mode real
```

Nota de arquitectura:

- `run --process-family o2c` ejecuta el pipeline determinista de preparación/validación O2C.
- En modo O2C, la CLI intenta autoload de fuentes SAP desde `raw_data/*.zip` del `input-zip` (tablas requeridas para entidades `fail_fast`).
- `run_rf15c_e2e_manual.py --process-family o2c` ejecuta el grafo multiagente (LangGraph + AlphaCodium + LLM + LangSmith).

Ver resumen legible del run (hipótesis, tests, hallazgos, score y explicación):

```bash
python3 scripts/show_run_summary.py --run-id rf15c14-real
```

Archivos clave para inspección manual:

- Hipótesis: `run_results/<run_id>/graph/hypotheses.json`
- Tests seleccionados: `run_results/<run_id>/graph/selected_tests.json`
- Hallazgos por test: `run_results/<run_id>/graph/findings.json`
- Clasificación final: `run_results/<run_id>/graph/scores.json`
- Explicación auditora: `run_results/<run_id>/graph/explanations.json`
- Runtime LLM por nodo: `run_results/<run_id>/graph/graph_state.json` en `run_metadata.llm_runtime_by_node`

Verificación RF15c (suite completa):

```bash
python3 -m pytest -q \
  tests/test_rf15c_graph_state.py \
  tests/test_rf15c_hypothesis_planner.py \
  tests/test_rf15c_test_planner.py \
  tests/test_rf15c_executor_node.py \
  tests/test_rf15c_explainer_node.py \
  tests/test_rf15c_explainer_repair.py \
  tests/test_rf15c_scoring_node.py \
  tests/test_rf15c_persist_node.py \
  tests/test_rf15c_multiagent_integration.py \
  tests/test_rf15c_end_to_end_contract.py \
  tests/test_rf15c_manual_e2e_script.py
```

Verificación RF14b (trazabilidad + evaluadores + dataset + experimentos):

```bash
python3 -m pytest -q \
  tests/test_rf14b_contracts.py \
  tests/test_rf14b_env_validation.py \
  tests/test_rf14b_evaluators.py \
  tests/test_rf14b_langsmith_dataset.py \
  tests/test_rf14b_experiments_script.py
```

Ejecutar experimentos RF14b-08:

```bash
python3 scripts/run_rf14b_experiments.py \
  --run-id-prefix rf14b-08 \
  --models-config config/models.yaml \
  --planner-baseline-model gpt-5.4-mini \
  --planner-candidate-model gpt-5.4 \
  --scoring-baseline-profile default \
  --scoring-candidate-profile conservative
```

Referencia RF14b:

- `docs/rf14b.md`
- `scripts/check_real_cloud_readiness.py` (cierre cloud-readiness con 3 runs reales)
- `docs/langsmith_experiments.md`
- `docs/langsmith_tracing_runbook.md`

Verificación RF18 (scoring):

```bash
python3 -m pytest -q \
  tests/test_rf18_score_schema.py \
  tests/test_rf18_scoring_prompt.py \
  tests/test_rf18_scoring_agent.py \
  tests/test_rf18_scoring_end_to_end.py \
  tests/test_rf15c_scoring_node.py \
  tests/test_rf15c_persist_node.py
```

Referencia funcional:

- `docs/scoring.md`

Nota:

- LangSmith no es obligatorio para ejecutar RF15c en local; la traza puede quedar en `N/A`.

Verificación RF15 (explainer + guardrails + persistencia + reporte):

```bash
python3 -m pytest -q \
  tests/test_rf15_explanation_schema.py \
  tests/test_rf15_explainer_prompt.py \
  tests/test_rf15_explainer_entity_and_run_summary.py \
  tests/test_rf15_validator_and_snapshot.py \
  tests/test_rf15c_explainer_node.py \
  tests/test_rf15c_explainer_repair.py \
  tests/test_rf15c_persist_node.py \
  tests/test_rf08_reporting.py
```

Referencia funcional:

- `docs/rf15.md`
- `docs/rf15_verification.md`

Opcional: adjuntar traza LangSmith manualmente:

```bash
python3 scripts/run_rf15c_e2e_manual.py \
  --run-id rf15c14-demo \
  --schema-summary-path schema_summary.json \
  --langsmith-trace-link "https://smith.langchain.com/..."
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
- `TST-ROUND-DOLLAR-PAYMENTS`
- `TST-JUST-BELOW-AUTH-THRESHOLD`
- `TST-SPLIT-PAYMENTS-NEAR-LIMIT`
- `TST-INVOICE-SEQUENCE-GAPS`
- `TST-NEGATIVE-QUANTITY-RECEIPTS`
- `TST-DUPLICATE-MATERIAL-ITEMS`
- `TST-UNUSUAL-POSTING-TIMES`
- `TST-LARGE-EVEN-DOLLAR-ENTRIES`

## Runner seguro RF04

- Ejecución solo de tests en allowlist (`tests/catalog`)
- Timeout por test (best-effort) opcional
- Continuidad si un test falla (`ERROR`) o expira (`TIMEOUT`)
- Persistencia de:
  - `test_runs.json`
  - `test_runner_logs.jsonl`

## Tools y Policies RF15b

- Configuración:
  - `config/tools_registry.yaml`
  - `config/agent_policies.yaml`
  - `config/query_templates.yaml`
- Componentes:
  - `PolicyEnforcer` (`src/erp_fraud/agents/policy_enforcer.py`)
  - `SchemaGuard` (`src/erp_fraud/agents/schema_guard.py`)
  - `query_allowlist` (`src/erp_fraud/agents/query_allowlist.py`)
  - `ToolCallLogger` (`src/erp_fraud/agents/tool_call_logging.py`)

Reglas:

- sin SQL libre (solo `query_template_id` allowlist),
- bloqueo de tool no autorizada por agente,
- bloqueo de referencia inexistente (`test_id`/tabla/columna),
- logging JSONL por llamada de tool con `params_hash`, `duration_ms`, `status`.

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
- Ranking agregado (RF07): `run_results/<run_id>/ranking.json` y opcional `ranking.parquet`
- Reporte RF08:
  - `run_results/<run_id>/report.json`
  - `run_results/<run_id>/report.md`
  - `run_results/<run_id>/report.html` (opcional)
  - validación de links vía `artifact_paths` en `report.json`
- Estructura de run RF10:
- `run_results/<run_id>/run_structure.json`
- artefactos KB (RF15e, si indexado activado):
  - `run_results/<run_id>/kb_index_manifest.json`
  - `run_results/<run_id>/kb_index_state.json`
- evidencias RF14 (cierre):
  - `run_results/rf14-17-check/pytest_rf14.log`
  - `run_results/rf14-17-check/verification_summary.json`
- evidencias AG03 (cierre):
  - `run_results/ag03-15-check/pytest_ag03.log`
  - `run_results/ag03-15-check/verification_summary.json`
