# RF15c — Multiagente (Planificador + Experto + Ejecutor + Scoring)

## Estado actual

Implementado hasta `RF15c-18`:

- `RF15c-01..06`: estado, prompts, hypothesis/test planner con allowlist y validaciones contra schema.
- `RF15c-07`: executor no-LLM con salida normalizada y `test_runs`.
- `RF15c-08..09`: explainer con citas obligatorias (`test_id`, `keys`, `evidence_columns`) + guardrails y reparación.
- `RF15c-10..11`: scoring con `fraud_type_probs` y validador de suma/procedencia de evidencias.
- `RF15c-12`: persistencia de `hypotheses.json`, `selected_tests.json`, `explanations.json/md`, `scores.json`.
- `RF15c-13`: integración CI con stubs (`LLM + KB + executor`).
- `RF15c-14`: ejecución manual E2E y captura de evidencia (LangSmith opcional).
- `RF15c-15`: documentación de agentes (`docs/agents.md`) con roles, tools, prompts y contratos.
- `RF15c-16`: test de integración E2E contractual (`tests/test_rf15c_end_to_end_contract.py`).
- `RF15c-17`: actualización de README/runbook para operación y verificación RF15c.
- `RF15c-18`: verificación ejecutada y evidencia documentada (`docs/rf15c_verification.md`).

## RF15c-14 (Manual E2E + Evidencia)

Script:

- `scripts/run_rf15c_e2e_manual.py`

Ejemplo de ejecución manual:

```bash
python3 scripts/run_rf15c_e2e_manual.py \
  --run-id rf15c14-demo \
  --schema-summary-path schema_summary.json \
  --catalog-path tests/catalog \
  --persist-base-dir run_results \
  --llm-mode stub \
  --langsmith-trace-link "https://smith.langchain.com/..."
```

Salida principal:

- `run_results/<run_id>/rf15c_14_manual_evidence.json`

Campos clave de evidencia:

- `graph_status`
- `node_status`
- `persist_manifest_path`
- `persist_artifacts`
- `langsmith`:
  - `tracing_enabled`
  - `api_key_present`
  - `project`
  - `endpoint`
  - `trace_link`
- `llm_mode` (`stub` o `real` reportado)

## Variables de entorno útiles (LangSmith)

- `LANGSMITH_TRACING=true`
- `LANGCHAIN_TRACING_V2=true`
- `LANGSMITH_API_KEY=...`
- `LANGSMITH_PROJECT=...`
- `LANGSMITH_ENDPOINT=...`
- `LANGSMITH_TRACE_LINK=...` (opcional, también aceptado por flag)

## Nota técnica

Actualmente el proyecto ejecuta nodos LLM en modo controlado/stub para CI y reproducibilidad.
El campo `llm_mode` en la evidencia permite dejar constancia explícita del modo usado en la demo.
LangSmith es opcional en esta entrega; si no se usa, la evidencia marca traza `N/A`.
