# Arquitectura del grafo multiagente (RF14)

## Objetivo

Documentar el grafo multiagente para que cualquier persona pueda:

1. entender el orden y propósito de cada nodo,
2. saber qué entra y qué sale de cada nodo,
3. reproducir una ejecución y depurar fallos.

## Diagrama del flujo



## Routing y control de ejecución

El orquestador (`src/erp_fraud/graph/graph.py`) soporta:

- **secuencia full**: `ingest -> kb_index -> hypothesis_planner -> test_planner -> executor -> explainer -> scoring -> persist -> second_level_explainer`
- **abort condicional** antes de planificación si:
  - `abort_graph=true`,
  - `schema_validation_failed=true`,
  - `ingest_status=ERROR`.
- **timeouts y retries por nodo** (configurables):
  - `graph_default_timeout_ms`
  - `graph_default_retries`
  - `graph_node_timeouts_ms` (override por nodo)
  - `graph_node_retries` (override por nodo)
- incluso en abort, si existe nodo `persist`, se intenta persistir artefactos.

## Estado compartido (GraphState)

Definido en `src/erp_fraud/graph/state.py`.

Campos principales:

- `run_id`
- `schema`
- `kb_status`
- `hypotheses`
- `selected_tests`
- `findings`
- `explanations`
- `scores`
- `run_metadata`

`run_metadata` actúa como bitácora técnica: estado por nodo, tiempos, intentos, errores y rutas de artefactos.

## Contrato por nodo (I/O)

### 1) `ingest`

- Entrada:
  - `run_metadata.db_path` o `run_metadata.schema_summary_path`
  - `run_metadata.schema_name` (opcional, default `main`)
- Salida:
  - `state.schema` poblado con `schema_summary`
  - `run_metadata.ingest_*` con trazas (`ingest_source`, `ingest_table_count`, etc.)

### 2) `kb_index`

- Entrada:
  - `run_metadata.kb_index_enabled`
  - paths de config KB (`kb_sources_config`, `kb_chunking_config`, `kb_chroma_config`)
- Salida:
  - `state.kb_status` (`OK`, `DISABLED` o `ERROR`)
  - trazas en `run_metadata` (`kb_index_status`, manifest/state path)

### 3) `hypothesis_planner` (agente)

- Entrada:
  - `state.schema`
  - catálogo (`run_metadata.catalog_path`)
  - flag opcional KB search (`run_metadata.kb_search_enabled`)
- Tools usadas (con policy RF15b):
  - `TestCatalog`
  - `Schema`
  - `RunStore` (stub actual)
  - KB opcional: `KBSearchTool` (RF15e)
- Salida:
  - `state.hypotheses` con hipótesis estructuradas y `tool_context`

### 4) `test_planner` (agente)

- Entrada:
  - `state.hypotheses`
  - catálogo de tests (allowlist)
- Lógica:
  - puntúa candidatos por keywords/fraud_type
  - filtra por allowlist
  - `top_n` configurable
- Salida:
  - `state.selected_tests` con `hypothesis_id`, `test_id`, `score`, `match_reasons`

### 5) `executor` (no-LLM)

- Entrada:
  - `state.selected_tests`
  - DB/config (`db_path`, `schema_name`, `table_name`)
- Lógica:
  - ejecuta tests reales via `TestRunner.run_all(...)`
- Salida:
  - `state.findings` (resultado estándar por test)
  - métricas en `run_metadata` (`executor_tests_count`, `executor_findings_total`)

### 6) `explainer` (agente explicador con guardrails)

- Entrada:
  - `state.findings`
- Guardrails:
  - solo `test_id` ejecutados
  - solo columnas existentes en `result.columns`
- Salida:
  - `state.explanations` (resumen por test)

### 7) `scoring` (híbrido: determinista + LLM opcional)

- Entrada:
  - `state.findings`
  - `weights.yaml`
- Lógica:
  - base determinista: agrega por `entity_key`, calcula `score_total` y distribución por `fraud_type`
  - modo real opcional: usa LLM para clasificación/probabilidades con validación de contrato y fallback controlado
- Salida:
  - `state.scores` con `ranking`, `fraud_type_distribution`, `summary`

### 8) `persist`

- Entrada:
  - todo el estado acumulado
- Salida en disco:
  - `run_results/<run_id>/graph/`
  - `hypotheses.json`, `selected_tests.json`, `findings.json`, `explanations.json`, `scores.json`, `graph_state.json`, `manifest.json`
- Trazas:
  - `run_metadata.persist_*`

### 9) `second_level_explainer` (agente LLM RF16, post-run)

- Entrada:
  - artefactos ya persistidos del run actual (`graph/*`)
  - opcionalmente runs previos para comparar (`rf16_compare_run_ids` o auto latest P2P+O2C)
- Lógica:
  - comparación determinista de runs (tests seleccionados, findings, fraud_types, similitud)
  - en `llm_mode=real` genera conclusiones/recomendaciones con schema validado y fallback determinista
- Salida:
  - `graph/second_level_analysis.json`
  - `graph/second_level_analysis.md`
  - recomendaciones en `state.recomendaciones`

## Nodos y agentes (qué es “agente” aquí)

En esta arquitectura, **agente = rol de decisión** dentro del nodo.  
No todos los nodos son LLM:

- Solo hay **4 agentes** en el flujo actual: `hypothesis_planner`, `test_planner`, `explainer`, `scoring`.
- Agentes/roles de decisión: `hypothesis_planner`, `test_planner`, `explainer`, `scoring`
- Nodos deterministas/no-LLM: `ingest`, `kb_index`, `executor`, `persist`
- Nodo híbrido: `scoring` (determinista en `stub`, LLM en `real`)

Esto permite control y auditabilidad: decisión asistida donde aporta valor, ejecución determinista donde hay riesgo.

## Relación con RF16 (explicador de 2º nivel)

RF16 se integra como nodo final/post-run en la secuencia full actual (`second_level_explainer`), pero conceptualmente consume artefactos ya persistidos (`run_results/.../graph/*`) para comparar ejecuciones entre sí (P2P/O2C o single-run) y proponer recomendaciones de auditoría. No forma parte del núcleo mínimo necesario para ejecutar pruebas antifraude.

Comandos RF16 integrados:

- `python3 -m src.erp_fraud.cli.main list-runs`
- `python3 -m src.erp_fraud.cli.main compare-runs ...`

Referencia: `docs/rf16.md`.

## Artefactos clave para depurar

- estado técnico:
  - `run_metadata.node_status`
  - `run_metadata.node_timings_ms`
  - `run_metadata.node_attempts`
  - `run_metadata.errors`
- outputs de negocio:
  - `graph/hypotheses.json`
  - `graph/selected_tests.json`
  - `graph/findings.json`
  - `graph/explanations.json`
  - `graph/scores.json`
- índice de artefactos:
  - `graph/manifest.json`

## Estado actual de implementación

Actualmente RF14 está implementado incrementalmente con tests por bloque y un integration test de `run_graph_full`.

Referencia:

- `docs/rf14.md`
