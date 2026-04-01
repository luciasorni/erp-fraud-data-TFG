# erp-fraud-data-TFG

Base del TFG para detección de fraude en ERP (fase inicial P2P) usando el dataset `ERP Fraud Data` y DuckDB.

## Documentación

- `docs/architecture.md`
- `docs/rf01.md`
- `docs/rf02.md`
- `docs/rf03.md`
- `docs/rf04.md`
- `docs/rf05.md`
- `docs/rf06.md`
- `docs/rf07.md`
- `docs/rf08.md`
- `docs/rf10.md`
- `docs/rf13.md`
- `docs/rf14.md`
- `docs/rf15.md`
- `docs/rf15_verification.md`
- `docs/rf15b.md`
- `docs/rf15c.md`
- `docs/rf15e.md`
- `docs/scoring.md`
- `docs/rf18_verification.md`
- `docs/agents.md`
- `docs/langgraph_architecture.md`
- `docs/alphacodium_workflow.md`
- `docs/ag03_iteraciones_reales.md`
- `docs/rag_kb.md`
- `docs/pre_langsmith_checklist.md`
- `docs/data.md`
- `docs/how_to_run.md`
- `docs/tools_and_policies.md`

## Alcance actual (Fase 1 - RF01 en progreso)

- Ingesta orientada a `joint_datasets/` (P2P, dataset plano)
- No se usa `raw_data/` en esta fase
- Carga a DuckDB local (`erp.duckdb`)
- Generación de artefactos reproducibles por ejecución:
  - `dataset_hash`
  - `schema_summary.json`
  - `run_metadata.json`
  - logs JSONL de ingesta

## Estructura relevante

- `src/erp_fraud/ingest/`: lectura del zip, validación, carga tabular, normalización y limpieza
- `src/erp_fraud/storage/`: DuckDB, rutas de salida, schema summary, run metadata y logging JSON
- `src/erp_fraud/agents/`: guardrails de tools y políticas por agente (RF15b)
- `tests/`: tests unitarios de la base de ingesta/storage
- `project/`: planificación y backlog del TFG (`.txt` + `.xlsx`)
- `run_results/<run_id>/`: salidas y evidencias de cada ejecución (local, no versionado)

## Qué está implementado (resumen)

- Lectura de `erp_fraud_data.zip` y localización de `joint_datasets/`
- Validación de ficheros esperados del dataset
- Carga robusta de CSV/Parquet desde zip a `pandas`
- Normalización de tipos (fechas, importes, IDs) y limpieza técnica mínima
- Conexión DuckDB + carga de tablas (`overwrite` / `append`)
- Métricas por tabla (`rows_loaded`, `duration_ms`)
- Cálculo de `dataset_hash` reproducible
- Generación de `schema_summary.json` y `run_metadata.json`
- Logging estructurado JSONL para ingesta
- Manejo de errores típicos (zip corrupto, CSV mal formado, parseos)

## Data Dictionary (RF02)

Se añadió una base de diccionario de datos para alinear tests y campos del dataset.

Artefactos:

- `data_dictionary.json`: formato máquina
- `data_dictionary.md`: formato humano

Capacidades actuales:

- Generar borrador desde `schema_summary.json` (tablas/columnas/tipos)
- Garantizar campos mínimos por entrada:
  - `table`, `column`, `type`, `description`, `examples`, `used_in_tests`
- Anotar `used_in_tests` desde catálogo de tests (`tests/catalog`)
- Validar completitud: falla si un test usa un campo no documentado

CLI disponible:

```bash
python3 -m src.erp_fraud.cli.main validate-dictionary \
  --dictionary data_dictionary.json \
  --catalog tests/catalog
```

Opcional:

- `--output-json` para resumen en JSON

Código de salida:

- `0`: diccionario completo
- `1`: faltan campos documentados usados por tests
- `2`: error de entrada/parseo

## Data Validation (RF02b)

Se añadió validación técnica previa a ejecución de tests, basada en columnas requeridas por `TestSpec`.

Checks implementados:

- `missing_required_columns` (critical)
- `type_parse_errors_dates` (critical)
- `type_parse_errors_amounts` (critical)
- `null_percentage_required_columns` (warning)
- `basic_ranges_dates` (warning)
- `basic_ranges_amounts` (warning)

Artefacto principal:

- `data_validation_report.json` (estructura estable, ordenada y con severidades)

Regla de bloqueo:

- el run se bloquea **solo** si hay errores `critical`
- si hay solo `warning`, el run continúa

## Fraud Test Catalog (RF03)

Se añadió un catálogo inicial versionado de tests antifraude (alineado con ACFE/COSO) con 2 controles P2P implementados.

Catálogo:

- `tests/catalog/tst_duplicate_postings.yaml`
- `tests/catalog/tst_unusual_amount_by_vendor.yaml`

Componentes:

- Esquema `TestSpec`: `src/erp_fraud/catalog/test_spec_schema.py`
- Loader y validación de `TestSpec`: `src/erp_fraud/catalog/test_spec_loader.py`
- Ejecución de tests y resultado estándar: `src/erp_fraud/catalog/test_execution.py`
- SQL de referencia: `sql/tests/`
- Changelog de catálogo: `tests/CHANGELOG.md`

Nota:

- `data_requirements.required_columns_exact` define columnas exactas por test para soporte de validación técnica previa (RF02b).

## Secure Test Runner (RF04)

Se añadió el motor de ejecución seguro base para catálogo:

- Allowlist de `test_id` (solo IDs existentes en `tests/catalog`)
- Continuidad ante fallo por test (`status=ERROR` + `error_summary`)
- Timeout por test best-effort (`status=TIMEOUT`)
- Métricas de tiempo:
  - por test
  - por fase (`selection`, `execution`, `total`)
- Persistencia de resultados de ejecución:
  - `test_runs.json` por run
- Logs por test:
  - `test_start` / `test_end` en JSONL con `run_id` y `test_id`

Componente principal:

- `src/erp_fraud/catalog/test_runner.py`

## Result Schema & Outputs (RF05)

Se añadió estandarización de salida por test y serialización reproducible.

Componentes:

- Contrato `ResultSchema`: `src/erp_fraud/catalog/result_schema.py`
- Validador: `src/erp_fraud/catalog/result_schema_validator.py`
- Convención de `entity_key`: `src/erp_fraud/catalog/entity_key.py`
- Writer por test: `src/erp_fraud/catalog/result_writer.py`

Salidas por test:

- `run_results/<run_id>/tests_outputs/<test_id>/findings.jsonl`
- `run_results/<run_id>/tests_outputs/<test_id>/findings.parquet` (opcional)
- `run_results/<run_id>/tests_outputs/<test_id>/sample_top20.json`

Reglas:

- validación de columnas obligatorias del resultado
- orden estable antes de escribir (reproducibilidad)
- sample top-N por test para reporte

## Drilldown Bidireccional (RF06)

Se añadió trazabilidad de hallazgos para reconstruir filas origen en DuckDB de forma segura.

Componentes:

- Keys mínimas por test (`drilldown_keys.py`)
- Plantillas seguras por `query_id` (`drilldown_templates.py`)
- Ejecutor de drilldown parametrizado (`drilldown.py`)
- CLI `drilldown` (`src/erp_fraud/cli/main.py`)

Ejemplo:

```bash
python3 -m src.erp_fraud.cli.main drilldown \
  --run-id <run_id> \
  --test-id TST-UNUSUAL-AMOUNT-BY-VENDOR \
  --entity-key "betrag=10296.0|kreditor=V1024"
```

## Agregador y Ranking (RF07)

Se añadió scoring y ranking reproducible de hallazgos multi-test:

- Config de pesos: `config/weights.yaml`
  - `defaults.severity_weights`
  - `overrides.by_test_id`
  - `ranking.top_k`
- Scoring: `src/erp_fraud/catalog/scoring.py`
  - `score_test = weight * metric_value`
- Agregación por entidad: `src/erp_fraud/catalog/ranking.py`
- Persistencia de ranking: `src/erp_fraud/catalog/ranking_writer.py`
  - `ranking.json`
  - `ranking.parquet` (opcional)

Reglas de reproducibilidad:

- orden estable por `score_total` desc + `entity_key` asc
- empate resuelto de forma determinista
- recorte opcional por `top_k`

## Reporte MVP (RF08)

Se añadió generación de reporte estructurado y legible:

- `report.json`:
  - contrato estable con `metadata`, `summary`, `ranking`, `test_runs`, `artifact_paths`, `errors`
  - rutas automáticas a evidencias (outputs por test + `data_dictionary` + `schema_summary`)
- `report.md`:
  - generado desde `report.json` con secciones fijas
- `report.html`:
  - render opcional desde Markdown (con fallback seguro)

Componentes:

- `src/erp_fraud/storage/report_json.py`
- `src/erp_fraud/storage/reporting.py`

Validación de links:

- `validate_report_json_file_artifact_links(...)` detecta artefactos no existentes en `artifact_paths`.

## Orquestación por Grafo (RF14)

Se implementó un grafo multiagente con ejecución por nodos y trazabilidad por estado:

- estado: `src/erp_fraud/graph/state.py`
- nodos: `src/erp_fraud/graph/nodes.py`
- orquestador/routing: `src/erp_fraud/graph/graph.py`
- documentación técnica:
  - `docs/rf14.md`
  - `docs/langgraph_architecture.md`

Verificación rápida RF14:

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

## Workflow AlphaCodium (AG03)

Se implementó el loop `Plan -> Draft -> Validate -> Repair` para nodos LLM del grafo:

- `hypothesis_planner`
- `test_planner`
- `expert_explainer`
- `scoring`

## Multiagente RF15c

Se añadió el flujo multiagente completo de planificación/ejecución/explicación/scoring:

- planner de hipótesis con `sources` trazables,
- selección de tests por allowlist y compatibilidad de schema,
- ejecución determinista de tests en catálogo (sin SQL libre),
- explicador con guardrails anti-alucinación + reparación,
- scoring con `fraud_type_probs` y validación de evidencia real,
- persistencia de artefactos RF15c:
  - `hypotheses.json`
  - `selected_tests.json`
  - `explanations.json`
  - `explanations.md`
  - `score.json`

Documentación principal:

- `docs/rf15c.md`
- `docs/agents.md`

Nota:

- LangSmith es opcional; el flujo funciona sin LangSmith configurado.

## LLM Experto y Explicaciones RF15

Se añadió la capa de explicación auditable sobre resultados reales del run:

- contrato de salida de explicación (`ExplanationSchema`),
- prompt con reglas anti-invención (columnas/test_id/keys/evidence_columns),
- validación cruzada contra catálogo + schema + findings,
- loop de reparación cuando la validación falla,
- persistencia y enlace en reporte.

Artefactos por run:

- `run_results/<run_id>/graph/explanation.json`
- `run_results/<run_id>/graph/explanation.md`
- alias de compatibilidad:
  - `run_results/<run_id>/graph/explanations.json`
  - `run_results/<run_id>/graph/explanations.md`

Reporte:

- `report.md` incluye sección `Explicaciones del agente` con enlaces a artefactos.

Referencia:

- `docs/rf15.md`
- `docs/rf15_verification.md`

## Scoring RF18

Se reforzó el módulo de scoring como contrato explícito (`ScoreSchema`) con validación y trazabilidad.

Piezas clave:

- contrato: `src/erp_fraud/catalog/score_schema.py`
- agente: `src/erp_fraud/catalog/scoring_agent.py`
- nodo grafo: `src/erp_fraud/graph/nodes.py` (`scoring_node`)
- perfiles de modelo: `config/models.yaml`
- documentación técnica: `docs/scoring.md`

Capacidades actuales:

- salida estructurada con `score_schema_version`, `fraud_type_probs`, `final_label`, `confidence`, `model_used`
- autocorrección por validación fallida (retry)
- selección de perfil/modelo por config sin tocar código
- comparación de dos perfiles:
  - `score_compare.json`
- integración opcional LangSmith no bloqueante:
  - `score_experiment.json` (`READY` o `SKIPPED`)

Componentes:

- loop reusable: `src/erp_fraud/agents/alpha_loop.py`
- integración en nodos: `src/erp_fraud/graph/nodes.py`
- evidencias reales documentadas: `docs/ag03_iteraciones_reales.md`

Verificación AG03:

```bash
python3 -m pytest -q \
  tests/test_ag03_alpha_loop_integration.py \
  tests/test_ag03_alpha_artifacts.py \
  tests/test_ag03_prompt_snapshots.py
```

## Comando Único (RF10)

Flujo completo en un solo comando:

```bash
/opt/anaconda3/bin/python -m src.erp_fraud.cli.main run --input-zip erp_fraud_data.zip
```

Atajo equivalente con Make:

```bash
make run INPUT_ZIP=erp_fraud_data.zip
```

Pipeline ejecutado:

1. Ingesta de zip y carga a DuckDB
2. Validación técnica de datos
3. Ejecución de tests de catálogo
4. Ranking agregado
5. Generación de reporte (`json`, `md`, `html`)

## RAG / KB Local (RF15e)

Se añadió un índice local en Chroma para fuentes ACFE + documentación del proyecto, con rebuild incremental por hash.

- Guía: `docs/rag_kb.md`
- Estado de implementación: `docs/rf15e.md`
- Módulos:
  - `src/erp_fraud/agents/kb_sources.py`
  - `src/erp_fraud/agents/kb_text_extractor.py`
  - `src/erp_fraud/agents/kb_chunking.py`
  - `src/erp_fraud/agents/kb_chroma.py`
  - `src/erp_fraud/agents/kb_index.py`
  - `src/erp_fraud/agents/kb_search.py`

## Catálogo ampliado RF13

Estado actual:

- selección priorizada ACFE documentada en `docs/rf13.md`,
- catálogo con TestSpecs activos en `tests/catalog/`,
- soporte de ejecución por subconjunto:
  - `--select-tests`
  - `--select-fraud-types`
  - `--select-tags`
- validación automatizada de catálogo contra `schema_summary` antes del run.

Opciones útiles:

- `--out-dir <ruta>`: carpeta raíz de runs (default: `run_results`)
- `--run-id <id>`: ID de run explícito
- `--select-tests TST-A,TST-B`: ejecutar subset
- `--top-k <n>`: override de top-k

## Tools y Políticas (RF15b)

Se añadió capa de guardrails para flujo multiagente:

- Registro de tools: `config/tools_registry.yaml`
- Políticas por agente/nodo: `config/agent_policies.yaml`
- Allowlist de queries parametrizadas: `config/query_templates.yaml`
- Enforcer runtime: `src/erp_fraud/agents/policy_enforcer.py`
- Validador anti-alucinación de referencias: `src/erp_fraud/agents/schema_guard.py`
- Logging de llamadas de tools: `src/erp_fraud/agents/tool_call_logging.py`

Comportamiento esperado:

- Si una tool no está permitida para el agente, se bloquea (`ToolPolicyDeniedError`).
- Si una referencia de tabla/columna/test no existe, se bloquea (`SchemaGuardValidationError`).
- Si una query template no está allowlist o los params son inválidos, se bloquea.
- `enforce_and_call(...)` puede registrar `tool_calls.jsonl` con:
  `tool_id`, `agent_id`, `params_hash`, `duration_ms`, `status`.

Verificación rápida RF15b:

```bash
/opt/anaconda3/bin/python -m pytest -q \
  tests/test_rf15b_tools.py \
  tests/test_rf15b_policy_and_schema_guard.py \
  tests/test_rf15b_tool_call_logging.py
```
- `--config <file.json|file.yaml>`: parámetros de run

Dónde ver resultados:

- `run_results/<run_id>/report.json`
- `run_results/<run_id>/report.md`
- `run_results/<run_id>/report.html`
- `run_results/<run_id>/ranking.json`
- `run_results/<run_id>/test_runs.json`

Drilldown desde un hallazgo:

```bash
/opt/anaconda3/bin/python -m src.erp_fraud.cli.main drilldown \
  --run-id <run_id> \
  --test-id <TEST_ID> \
  --entity-key "<ENTITY_KEY>" \
  --save-default
```

Atajos de calidad:

```bash
make test
make test-rf08
```

Verificación mínima de RF10:

```bash
/opt/anaconda3/bin/python -m src.erp_fraud.cli.main run --help
make test-rf08
```

Dependencias mínimas (si preparas un venv con red):

```bash
./.venv/bin/pip install -r requirements.txt
```

## Cómo verificarlo (actual)

Ejecutar tests unitarios de la base de ingesta/storage:

```bash
/opt/anaconda3/bin/python -m pytest -q tests/test_rf01_ingest_storage.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf02_data_dictionary.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf02b_data_validation.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf03_catalog.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf04_runner.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf05_result_schema_and_writer.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf06_drilldown.py tests/test_rf06_drilldown_components.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf07_ranking.py
/opt/anaconda3/bin/python -m pytest -q tests/test_rf08_reporting.py
```

Resultado esperado:

- RF01: `9 passed` (puede variar si se amplían tests)
- RF02: `6 passed` (puede variar si se amplían tests)
- RF02b: `4 passed` (puede variar si se amplían tests)
- RF03: `4 passed` (puede variar si se amplían tests)
- RF04: `6 passed` (puede variar si se amplían tests)
- RF05: `6 passed` (puede variar si se amplían tests)
- RF06: `6 passed` (puede variar si se amplían tests)
- RF07: `6 passed` (puede variar si se amplían tests)
- RF08: `6 passed` (puede variar si se amplían tests)

## Notas

- El dataset grande `erp_fraud_data.zip` está trackeado con Git LFS.
- La ejecución inicial de tests de catálogo está implementada en RF03; el motor de ejecución completo y endurecido se extiende en `RF04`.
