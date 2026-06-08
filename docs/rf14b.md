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
2. Etiquetas recomendadas: `rf14b`, `multiagent-graph`, `p2p`, `tfg`.

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

- `RF14b-02`: instrumentar trazas por nodo/agente en el grafo multiagente propio.
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

## RF14b-07 (estado implementado en código)

Dataset de evaluación generado por run:

- Se crea artefacto local:
  - `run_results/<run_id>/graph/langsmith_eval_dataset.jsonl`
- Contenido por ejemplo:
  - `inputs`: `hypotheses`, `findings`, `kb_snippets`
  - `outputs`: `final_label`, `fraud_type_probs`, `explanations`
  - `metadata`: `dataset_hash`, `graph_status`, `scoring_model_used`, `scoring_prompt_hash`

Publicación opcional a LangSmith:
- desactivada por defecto (`enable_langsmith_dataset_publish=false`)
- si se activa, intenta publicar dataset + examples y registra resultado en:
  - `run_metadata["langsmith_eval_dataset"]["publish"]`

## RF14b-08 (estado implementado en código)

Ejecución reproducible de 2 experimentos y comparativa de outputs:

- Script:
  - `scripts/run_rf14b_experiments.py`
- Test:
  - `tests/test_rf14b_experiments_script.py`

Qué ejecuta:

1. Experimento Planner
   - corre dos runs (`hypothesis_planner -> test_planner`) con dos modelos distintos para planner
   - compara:
     - `selected_tests`
     - `hypothesis_ids`

2. Experimento Scoring
   - corre un run de `scoring` con `scoring_compare_profiles=[baseline,candidate]`
   - compara:
     - modelo baseline vs candidato
     - `final_label`
     - `confidence_delta`
     - deltas por `fraud_type` (vía `score_compare`)

Artefactos generados:

- `run_results/<run_id_prefix>-rf14b08/rf14b_experiments.json`
- `run_results/<run_id_prefix>-rf14b08/rf14b_experiments.md`

Comando:

```bash
python3 scripts/run_rf14b_experiments.py \
  --run-id-prefix rf14b-08 \
  --models-config config/models.yaml \
  --planner-baseline-model gpt-5.4-mini \
  --planner-candidate-model gpt-5.4 \
  --scoring-baseline-profile default \
  --scoring-candidate-profile conservative
```

## RF14b-09 (estado implementado en código)

Informe de experimento generado y documentado en:

- `docs/langsmith_experiments.md`

Este informe recoge:

- comando reproducible de RF14b-08
- artefactos JSON/MD generados
- resumen de resultados baseline vs candidate para planner y scoring
- conclusiones para continuar con RF14b-10 (guía de ejecución local/cloud)

## RF14b-10 (estado implementado en código)

Runbook operativo local/cloud:

- `docs/langsmith_tracing_runbook.md`

Incluye:

- variables obligatorias y recomendadas
- comando de validación de entorno (`validate_required_env.py --profile langsmith`)
- ejecución local del pipeline y de experimentos RF14b-08
- checklist de verificación de trazas y troubleshooting

## RF14b-11 (estado implementado en código)

Tests de integración RF14b:

- `tests/test_rf14b_contracts.py`
- `tests/test_rf14b_env_validation.py`
- `tests/test_rf14b_evaluators.py`
- `tests/test_rf14b_langsmith_dataset.py`
- `tests/test_rf14b_experiments_script.py`

Además, el gate `scripts/run_pre_langsmith_gate.py` se amplió para incluir los tests RF14b.

## RF14b-12 (estado implementado en código)

Documentación actualizada:

- `README.md` (sección RF14b + comandos de experimentos)
- `docs/how_to_run.md` (comandos de verificación RF14b)
- `docs/langsmith_experiments.md` (informe de resultados)
- `docs/langsmith_tracing_runbook.md` (runbook local/cloud)

## RF14b-13 (estado implementado en código)

Verificación ejecutada y evidencia guardada en:

- `docs/rf14b_verification.md`
- `run_results/rf14b-13-check/verification_summary.json`
- `run_results/rf14b-13-check-rf14b08/rf14b_experiments.json`
- `run_results/pre_langsmith_gate.json`

## Endurecimiento runtime real (actualización)

Se añadió fallback seguro para modo real:

- Llamadas OpenAI con `timeout + retries` controlados.
- Si falla llamada LLM o validación de guardrails en nodo LLM:
  - reintenta via Alpha loop,
  - si sigue fallando, cae a salida determinista (fallback),
  - **no aborta el run completo**.

Observabilidad por nodo en `run_metadata["llm_runtime_by_node"]`:

- `model_used`, `llm_mode`, `latency_ms`
- `input_tokens`, `output_tokens`, `total_tokens`
- `cost_estimated_usd`, `retries_done`, `fallback_used`, `status`

Umbral operativo simple (monitorización, no bloqueo):

- Objetivo: `fallback_used=False` en todos los nodos LLM.
- Alerta: si más de 1 nodo LLM cae en fallback en un run real.
- Criterio pre-cloud recomendado: en 3 runs reales consecutivos, fallback total <= 1 nodo acumulado.

Nota:
- Este umbral se usa para seguimiento operativo.
- No bloquea CI normal (stub) ni runs locales; sirve para detectar degradación temprana.

CI en dos carriles:

- `ci.yml`: carril normal/stub (estable y barato).
- `real-smoke.yml`: carril real separado (manual/nightly, coste controlado).
