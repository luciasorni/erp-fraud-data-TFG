# RF14b — LangSmith (Trazabilidad y Evaluación)

Este documento explica RF14b en formato práctico.

## Qué es LangSmith (en este proyecto)

LangSmith nos sirve para 3 cosas:

1. Ver la traza del grafo por nodos/agentes (qué entró, qué salió, dónde falló).
2. Comparar ejecuciones/modelos con evidencia reproducible.
3. Medir evaluaciones automáticas (si una salida cumple esquema y guardrails).

No sustituye al pipeline: añade observabilidad y evaluación encima de lo que ya ejecuta el proyecto.

## RF14b-01 — Setup mínimo

### 1) Crear proyecto en LangSmith (UI)

En `smith.langchain.com`:

1. Crea un proyecto con nombre recomendado: `erp-fraud-tfg`.
2. Etiquetas recomendadas: `rf14b`, `langgraph`, `p2p`, `tfg`.

### 2) Configurar variables de entorno

Variables mínimas:

- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`

Opcionales:

- `LANGSMITH_TRACING=true`
- `LANGCHAIN_TRACING_V2=true`
- `LANGSMITH_ENDPOINT` (si usas endpoint no estándar)

Ejemplo local:

```bash
export LANGSMITH_API_KEY="tu_api_key"
export LANGSMITH_PROJECT="erp-fraud-tfg"
export LANGSMITH_TRACING="true"
export LANGCHAIN_TRACING_V2="true"
```

### 3) Validar que el setup está correcto

```bash
python3 scripts/validate_required_env.py --profile langsmith
```

Si falla, falta alguna variable obligatoria.

## Estado actual del código (hoy)

- El proyecto ya captura snapshot de configuración LangSmith en nodos de grafo.
- Si LangSmith no está configurado, el flujo **no se bloquea** (modo opcional/no bloqueante).
- RF14b continúa con instrumentación de trazas por nodo y datasets/experimentos de evaluación.

## Qué haremos después de RF14b-01

- `RF14b-02`: instrumentar trazas por nodo/agente en LangGraph.
- `RF14b-05...08`: evaluaciones automáticas + dataset de evaluación + comparativa de modelos.

## RF14b-02 (estado implementado en código)

Ya está instrumentado en el runner del grafo:

- `run_metadata["node_trace_events"]` guarda eventos `start/end` por nodo con:
  - `node_id`, `stage`, `attempt`, `status`, `duration_ms`
  - `input_summary` / `output_summary` (resumen de estado, no payload masivo)
  - `error` cuando aplica
- `run_metadata["langsmith"]` guarda snapshot de configuración detectada:
  - `tracing_enabled`, `api_key_present`, `project`, `endpoint`, `configured`

Objetivo práctico:
- Aunque todavía no hagamos evaluación de experimentos en LangSmith, ya tienes trazabilidad
  uniforme por nodo para depurar y para mapear 1:1 con trazas externas en los siguientes pasos.

## RF14b-03 (estado implementado en código)

Versionado de prompts + hash en metadata:

- Registro central: `config/prompt_versions.yaml`
  - `node_id -> file + version`
- Cargador de prompts: `src/erp_fraud/graph/prompt_registry.py`
- Registro por run en `run_metadata`:
  - `hypothesis_prompt_path|version|hash|status`
  - `test_planner_prompt_path|version|hash|status`
  - `explainer_prompt_path|version|hash|status`
  - `scoring_prompt_path|version|hash|status`

Además, la validación de esquema/config ahora comprueba que:
- existe `config/prompt_versions.yaml`
- cada prompt referenciado existe y tiene `version`.

## RF14b-04 (estado implementado en código)

Registro de `model_config` por nodo/agente en `run_metadata`:

- Config base: `config/models.yaml` sección `graph_nodes`.
- Se guarda en `run_metadata["agent_model_config"]` para:
  - `hypothesis_planner`
  - `test_planner`
  - `executor` (deterministic/sql runner)
  - `expert_explainer`
  - `scoring`

Campos mínimos registrados por nodo:
- `mode`
- `model_used`
- `temperature`
- `max_tokens`
- `models_config_path`
- `source`

## RF14b-05 (estado implementado en código)

Evaluadores automáticos añadidos (post-run) en `run_metadata["rf14b_evaluation"]`:

- `schema_allowlist_compliance`
  - verifica que `selected_tests` y `findings` solo usan `test_id` del catálogo.
- `no_invented_columns_or_test_ids`
  - verifica consistencia explicación↔findings (sin columnas/test_ids inventados).
- `kb_citations_present`
  - si `explainer_kb_enabled=true`, exige citas KB (`acfe_reference.hits`) por explicación.
  - si KB está desactivado, marca `SKIPPED_KB_DISABLED`.

## RF14b-06 (estado implementado en código)

Métrica de correspondencia fraude (`fraud_correspondence`) añadida dentro de `rf14b_evaluation`:

- compara `fraud_type` observados en `findings` con:
  - `scores[0].final_label`
  - `scores[0].fraud_type_probs[*].fraud_type`
- calcula `coherence_ratio = |intersección| / |fraud_types_en_findings|`.
- regla de pase:
  - `final_label` debe estar presente en los `fraud_type` de findings (si existe),
  - `coherence_ratio >= 0.5`.
