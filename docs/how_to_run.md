# Cómo Ejecutar (Local)

## Pre-requisitos

- Python del entorno local (en este proyecto se está usando Anaconda para tests)
- Dataset `erp_fraud_data.zip` disponible en raíz del repo
- Git LFS instalado para clonar correctamente el zip trackeado

## Comandos útiles

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
  --select-tests TST-DUPLICATE-POSTINGS,TST-UNUSUAL-AMOUNT-BY-VENDOR \
  --top-k 20

# Ejecutar subset por fraud_type/tags (RF13-05)
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --select-fraud-types duplicate_payment,amount_anomaly \
  --select-tags p2p,acfe

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
```

Calidad rápida:

```bash
make test
make test-rf08
```

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
