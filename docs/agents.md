# RF15c Agents — Roles, Tools y Contratos

## Objetivo

Documentar el flujo multiagente RF15c para que sea auditable y extensible sin romper guardrails.

Secuencia (grafo full):

`ingest -> kb_index -> hypothesis_planner -> test_planner -> executor -> explainer -> scoring -> persist`

## Clasificación oficial (actual)

En RF15c hay **4 agentes**:

1. `hypothesis_planner`
2. `test_planner`
3. `explainer`
4. `scoring` (híbrido: determinista en `stub`, LLM en `real`)

El resto son **nodos técnicos (no agentes)**:

- `ingest`
- `kb_index`
- `executor`
- `persist`

## Roles y nodos

### 1) Hypothesis Planner (`hypothesis_planner`)

Responsabilidad:

- generar hipótesis iniciales por `fraud_type` y `process_step`,
- adjuntar `sources` trazables,
- respetar schema/catálogo (sin referencias inventadas).

Salida principal:

- `state.hypotheses[]` con:
  - `hypothesis_id`, `title`, `description`,
  - `fraud_type`, `process_step`,
  - `evidence_requirements`,
  - `candidate_test_ids`,
  - `sources`.

Tools:

- `TestCatalog`
- `Schema`
- `DataCatalog`
- `KBSearch` (opcional, si habilitado)
- `RunStore` (persistencia de hipótesis)

Prompt:

- `prompts/hypothesis_planner.md`

### 2) Test Planner (`test_planner`)

Responsabilidad:

- seleccionar tests del catálogo para cada hipótesis,
- aplicar allowlist estricta (`test_id` existentes),
- filtrar tests incompatibles con schema.

Salida principal:

- `state.selected_tests[]`
- `state.recomendaciones[]`

Guardrails:

- no test fuera de catálogo,
- descarte automático si faltan `required_columns` en `schema_summary`.

Prompt:

- `prompts/test_planner.md`

### 3) Executor (`executor`)

Responsabilidad:

- ejecutar tests seleccionados (sin LLM),
- producir findings normalizados.

Salida principal:

- `state.findings[]` (ResultSchema-like por test),
- `state.test_runs[]` (resumen por test).

Nota:

- detección de fraude base es determinista (tests SQL/Python de catálogo).

### 4) Expert Explainer (`explainer` / `expert_explainer`)

Responsabilidad:

- explicar findings con citas explícitas,
- aplicar anti-alucinación y reparación.

Salida principal:

- `state.explanations[]` con:
  - `test_id`, `cited_test_id`,
  - `cited_keys`,
  - `cited_evidence_columns`,
  - `referenced_columns`,
  - `summary`,
  - `acfe_reference` (KB opcional).

Prompt:

- `prompts/explainer.md`

### 5) Scoring (`scoring`)

Responsabilidad:

- agregar hallazgos y generar ranking,
- estimar probabilidades por tipología.

Salida principal:

- `state.scores[0]`:
  - `ranking`,
  - `fraud_type_distribution`,
  - `fraud_type_probs`,
  - `summary`.
- `state.fraud_type_predicho[]`
- `state.ranking[]`

Prompt:

- `prompts/scoring.md`
- metodología y limitaciones: `docs/scoring.md`

## Tools permitidas (resumen)

Configuración fuente:

- `config/tools_registry.yaml`
- `config/agent_policies.yaml`

Mapa simplificado:

- `expert_recommender`: `TestCatalog`, `Schema`, `DataCatalog`, `RunStore` (+ `KBSearch` opcional por feature flag)
- `test_executor`: `DuckDBQuery`, `TestCatalog`, `Schema`, `RunStore`
- `scorer_classifier`: `RunStore`, `Schema`, `TestCatalog`
- `explainer`: `Schema`, `RunStore`
- `exporter`: `RunStore`

## Esquemas/contratos usados

- `GraphState`: `src/erp_fraud/graph/state.py`
- `TestSpec`: `src/erp_fraud/catalog/test_spec_schema.py`
- `ResultSchema`: `src/erp_fraud/catalog/result_schema.py`

Validadores clave:

- hipótesis: `fraud_type/process_step/evidence_requirements` válidos,
- selección: `test_id` allowlist + compatibilidad schema,
- explicación: guardrails anti-alucinación + reparación,
- scoring: `fraud_type_probs` suma ~1 y evidencia real.

## Ejemplo de ejecución

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
  tests/test_rf15c_multiagent_integration.py
```
