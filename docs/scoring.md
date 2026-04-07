# RF18 — Scoring por Tipología (ScoreSchema)

## Objetivo

Definir un scoring auditable y reproducible por tipología de fraude a partir de:

- hipótesis (`hypotheses`)
- hallazgos ejecutados (`findings`)
- contexto ACFE (`acfe_snippets`)

El resultado debe cumplir `ScoreSchema` y quedar trazado en metadata/artefactos.

## Contrato de salida

Contrato implementado en:

- `src/erp_fraud/catalog/score_schema.py`

Campos obligatorios:

- `score_schema_version`
- `generated_at_utc`
- `fraud_type_probs`
- `final_label`
- `confidence`
- `evidence_summary`
- `model_used`

## Implementación actual

### 1) Agente de scoring

- `src/erp_fraud/catalog/scoring_agent.py`

Responsabilidades:

- construir score a partir de `hypotheses + findings + acfe_snippets`
- parsear/normalizar salida
- exigir campos requeridos del `ScoreSchema`

### 2) Nodo de scoring del grafo

- `src/erp_fraud/graph/nodes/scoring.py` (`scoring_node`)

Responsabilidades:

- calcular ranking por entidad (compatibilidad con RF07/RF14)
- generar score estructurado (`ScoreSchema`)
- enriquecer `fraud_type_probs` con trazabilidad:
  - `source_test_ids`
  - `source_hypothesis_ids`
  - `acfe_chunk_ids`
- registrar metadatos de trazabilidad:
  - `scoring_model_used`
  - `scoring_prompt_hash`
  - `scoring_score_hash`

## Validaciones de scoring

Validadores en:

- `src/erp_fraud/graph/nodes/scoring.py`

Reglas activas:

1. `fraud_type_probs` es lista válida y cada probabilidad está en `[0,1]`.
2. Suma de probabilidades aproximada a `1.0` (tolerancia).
3. `final_label` debe existir dentro de `fraud_type_probs`.
4. Tipologías deben ser coherentes con `findings/hypotheses`.
5. `evidence_summary` debe referenciar `test_id` reales.

## Autocorrección (retry)

Si el primer output no pasa validación:

- se ejecuta ciclo de reparación en `alpha_loop`
- se corrige payload (normalización de probs, `final_label`, evidencia)
- se revalida antes de aceptar

Esto mantiene comportamiento robusto sin romper reproducibilidad.

## Modelos por configuración (sin tocar código)

Configuración:

- `config/models.yaml`

Selección en runtime:

- `run_metadata["models_config"]`
- `run_metadata["scoring_model_profile"]`

Resolución:

- `load_models_config(...)`
- `resolve_scoring_model(...)`

Perfiles iniciales:

- `default`
- `conservative`
- `exploratory`

## Comparación de modelos

Cuando se proporcionan dos perfiles en:

- `run_metadata["scoring_compare_profiles"]`

se genera:

- `run_metadata["score_compare"]`
- artefacto `graph/score_compare.json`

Incluye:

- perfil/modelo baseline y candidato
- cambio de `final_label`
- `confidence_delta`
- deltas por `fraud_type`

## Integración LangSmith (opcional, no bloqueante)

Estado actual:

- integración de RF18-09 es opcional y no depende de RF14b
- si no hay configuración, queda `SKIPPED`
- si hay entorno configurado, queda `READY`

Variables leídas:

- `LANGSMITH_TRACING` / `LANGCHAIN_TRACING_V2`
- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `LANGSMITH_ENDPOINT`
- `LANGSMITH_TRACE_LINK`

Artefacto:

- `graph/score_experiment.json`

## Artefactos generados por run (grafo)

- `run_results/<run_id>/graph/scores.json`
- `run_results/<run_id>/graph/score_compare.json` (si aplica)
- `run_results/<run_id>/graph/score_experiment.json` (si aplica)

## Limitaciones actuales

1. El proyecto está en modo `LLM-ready` con ejecución controlada/stub para reproducibilidad y CI.
2. La detección base sigue anclada en tests deterministas del catálogo.
3. La parte de experimentación externa (trazas remotas completas) está preparada, pero no es obligatoria en esta fase.

## Verificación rápida

```bash
python3 -m pytest -q \
  tests/test_rf18_score_schema.py \
  tests/test_rf18_scoring_prompt.py \
  tests/test_rf18_scoring_agent.py \
  tests/test_rf15c_scoring_node.py
```
