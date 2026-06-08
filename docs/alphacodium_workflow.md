# AG03 - Workflow AlphaCodium

## Objetivo

Definir una forma estándar de trabajar con AlphaCodium con aprobación humana:

1. AlphaCodium genera propuestas (prompts, código, tests, docs).
2. Validadores automáticos comprueban seguridad y consistencia.
3. Revisión humana decide integración.

## Cómo se une AlphaCodium con el grafo multiagente propio

Unión real en código:

- Grafo: `src/erp_fraud/graph/graph.py`
- Nodos: `src/erp_fraud/graph/nodes/` (paquete modular)
- Loop reusable: `src/erp_fraud/agents/alpha_loop.py`

Punto de integración:

- Los nodos LLM (`hypothesis_planner`, `test_planner`, `expert_explainer`, `scoring`) llaman a `_run_alpha_loop_for_node(...)`.
- `_run_alpha_loop_for_node(...)` ejecuta `alpha_loop(...)` con:
  - `prompt_text`
  - `input_payload`
  - `validators`
  - `max_iter`
- Resultado:
  - si pasa validación: se acepta `final_output`.
  - si no pasa y agota iteraciones: estado `ERROR`.

Para qué usamos AlphaCodium en este proyecto:

1. Forzar validación antes de aceptar salida LLM.
2. Evitar invenciones (test_id/columnas/keys fuera de contexto).
3. Dejar evidencia auditable por iteración en `run_results/<run_id>/alphacodium/...`.

## Qué puede generar AlphaCodium

- Plantillas de prompts en `prompts/`.
- Código en `src/` para nodos, validadores y wrappers.
- Tests en `tests/`.
- Documentación en `docs/`.

## Qué debe revisarse manualmente

1. Seguridad:
- no SQL libre.
- solo allowlists (`tools`, `query_template_id`, `test_id`).

2. Trazabilidad:
- no inventar `table.column`, `test_id`, `keys`.
- mantener evidencia reproducible en `run_results/`.

3. Impacto funcional:
- cambios en outputs deben estar justificados.
- documentación actualizada si cambia comportamiento.

## Checklist PR (AG03-04)

Marcar todo antes de merge:

- [ ] Pasa unit tests relevantes del cambio.
- [ ] Pasa al menos 1 integration test/smoke test del flujo afectado.
- [ ] No introduce SQL libre ni bypass de allowlists.
- [ ] No rompe validaciones de `PolicyEnforcer` / `SchemaGuard` (si aplica).
- [ ] No cambia outputs deterministas sin justificarlo en la PR.
- [ ] Si cambian artefactos/contratos, se actualiza documentación (`README`/`docs/*`).
- [ ] Se incluyen evidencias de ejecución (logs/tests) cuando el requisito lo exige.

## Comandos mínimos de verificación

```bash
# Suite base por módulos principales implementados
/opt/anaconda3/bin/python -m pytest -q \
  tests/test_rf03_catalog.py \
  tests/test_rf04_runner.py \
  tests/test_rf07_ranking.py \
  tests/test_rf08_reporting.py

# Guardrails de AG/RF15b
/opt/anaconda3/bin/python -m pytest -q \
  tests/test_rf15b_tools.py \
  tests/test_rf15b_policy_and_schema_guard.py \
  tests/test_rf15b_tool_call_logging.py
```

## Evidencia recomendada en PR

1. Resumen del cambio (qué y por qué).
2. Salida de tests ejecutados.
3. Riesgos conocidos y mitigación.
4. Si hubo iteraciones con prompt: `prompt -> output -> validación -> fix`.

## Evidencias AG03-12 (memoria/defensa)

Se documentaron 3 iteraciones reales en:

- `docs/ag03_iteraciones_reales.md`

Incluye:

- 1 caso con reparación (`REPAIR` -> `OK`) en `hypothesis_planner`.
- 2 casos `OK` en primera iteración (`test_planner`, `expert_explainer`).
- rutas exactas de artefactos en `run_results/<run_id>/alphacodium/...`.

## Registro de evidencias de iteración (AG03-06)

Para cada run con AlphaCodium, guardar evidencias en:

- `run_results/<run_id>/alphacodium/`

Estructura mínima por nodo/agente:

- `run_results/<run_id>/alphacodium/<node_id>/iteration_001/`
  - `prompt.md`
  - `output.json`
  - `validation.json`
  - `fix.diff` (si hubo reparación)
- `run_results/<run_id>/alphacodium/<node_id>/iteration_002/`
  - ...

Además, un resumen por nodo:

- `run_results/<run_id>/alphacodium/<node_id>/iterations_manifest.jsonl`

Campos mínimos por línea de `iterations_manifest.jsonl`:

- `run_id`
- `node_id`
- `iteration`
- `status` (`OK`, `REPAIR`, `ERROR`)
- `prompt_hash`
- `output_hash`
- `validation_passed` (`true/false`)
- `validation_errors` (lista)
- `timestamp_utc`

Flujo recomendado por iteración:

1. Guardar `prompt.md` (input exacto enviado al nodo LLM).
2. Guardar `output.json` (salida cruda estructurada).
3. Ejecutar validadores (`PolicyEnforcer`, `SchemaGuard`, schema output).
4. Guardar `validation.json` con resultado y errores.
5. Si falla, generar `fix.diff` con corrección aplicada y repetir iteración.
6. Registrar evento en `iterations_manifest.jsonl`.

Reglas:

- No sobrescribir iteraciones anteriores.
- Numeración incremental (`iteration_001`, `iteration_002`, ...).
- Toda reparación debe dejar traza (`fix.diff` o campo equivalente en `validation.json`).
- Si se aborta por `max_iter`, registrar último estado en manifest.

Plantilla mínima de `validation.json`:

```json
{
  "validation_passed": false,
  "checks": [
    {"name": "schema_guard", "passed": false, "detail": "columna no existe: main.fraud_1.X"},
    {"name": "policy_enforcer", "passed": true, "detail": "ok"},
    {"name": "output_schema", "passed": false, "detail": "falta campo evidence"}
  ],
  "repair_action": "ajustar columnas a schema_summary y regenerar output"
}
```

## AlphaCodium Loop estándar (AG03-07)

Este loop se aplica a todos los nodos LLM:

- `hypothesis_planner`
- `test_planner`
- `expert_explainer`
- `scoring`

Fases obligatorias por iteración:

1. **Plan**
- Leer objetivo del nodo y constraints activas.
- Seleccionar fuentes permitidas (`Schema`, `TestCatalog`, `RunStore`, etc. según policy).
- Definir plan breve de salida esperada.

2. **Draft**
- Generar `output.json` con esquema estructurado del nodo.
- No ejecutar acciones fuera de tools permitidas.

3. **Validate**
- Ejecutar validaciones técnicas:
  - `PolicyEnforcer` (tool allowlist/limits)
  - `SchemaGuard` (tabla/columna/test_id existentes)
  - validador de esquema de salida del nodo
- Registrar resultado en `validation.json`.

4. **Repair**
- Si `Validate` falla, construir reparación concreta (qué corregir y cómo).
- Regenerar salida en nueva iteración conservando trazabilidad.

Criterios de parada:

- `validation_passed = true` -> `status=OK`, fin del loop.
- `iteration == max_iter` y sigue fallando -> `status=ERROR`, abortar con evidencia.

Pseudocódigo del estándar:

```text
for i in 1..max_iter:
  plan = build_plan(input, constraints)
  draft = generate_output(plan)
  validation = run_validators(draft)
  save_iteration_artifacts(i, plan, draft, validation)
  if validation.passed:
    return OK(draft)
  draft_input = build_repair_feedback(validation.errors)
return ERROR(last_validation_errors)
```

Implementación reusable:

- `src/erp_fraud/agents/alpha_loop.py`
  - `alpha_loop(...)`
  - `AlphaLoopResult`

Matriz de validación mínima por nodo:

1. `hypothesis_planner`
- valida `test_id` y `table.column` referenciados en hipótesis.

2. `test_planner`
- valida que todos los `test_id` propuestos existen en catálogo.

3. `expert_explainer`
- valida citas a `evidence_columns` y `keys` reales.

4. `scoring`
- valida entidades existentes y consistencia de campos de score.

## CI (AG03-05)

Workflow configurado:

- `.github/workflows/ci.yml`

Checks que ejecuta:

1. `ruff check src tests scripts`
2. `python scripts/validate_project_schema.py`
3. `python scripts/dry_run_alphacodium_stub.py`
4. `python -m pytest -q` (suite completa del repositorio)

Historial de actualizaciones CI relevantes (sí, se ha ido ampliando por requisitos):

- `04e13c8`: primera base AG03 (workflow + dry-run).
- `20b6084`: ajuste de tooling/lint para estabilidad.
- `8b49055`: ampliación por RF13 (tests P1/catálogo).
- `258f84b`: robustez de CI (`python -m ...` y estabilidad general).
- Estado actual: CI ejecuta `python -m pytest -q` (cobertura completa), además de lint + schema validation + dry-run AlphaCodium.

## AG03-08 - Implementación de `alpha_loop()` reusable

Implementado en:

- `src/erp_fraud/agents/alpha_loop.py`

Capacidades:

- recibe `prompt + input + validators + max_iter`.
- ejecuta ciclo `Plan -> Draft -> Validate -> Repair`.
- persiste por iteración:
  - `prompt.md`
  - `output.json`
  - `validation.json`
  - `fix.diff` (si aplica)
  - `iterations_manifest.jsonl`

Test relacionado:

- `tests/test_ag03_alpha_artifacts.py`

## AG03-09 - Integración de `alpha_loop` en nodos LLM

Integrado en:

- `hypothesis_planner_node`
- `test_planner_node`
- `expert_explainer_node` (alias sobre explainer)
- `scoring_node`

Código:

- `src/erp_fraud/graph/nodes/planning.py` (`_run_alpha_loop_for_node(...)`)
- `src/erp_fraud/graph/nodes/explainer.py` (`_run_alpha_loop_for_node(...)`)
- `src/erp_fraud/graph/nodes/scoring.py` (`_run_alpha_loop_for_node(...)`)

Test relacionado:

- `tests/test_ag03_alpha_loop_integration.py`

## AG03-10 - Artefactos AlphaCodium por run

Persistencia y registro:

- artefactos por nodo en `run_results/<run_id>/alphacodium/...`
- resumen agregado en `persist_node` dentro de:
  - `run_results/<run_id>/graph/manifest.json` (campo `alphacodium`)
  - `run_metadata["alphacodium_artifacts"]`

Test relacionado:

- `tests/test_ag03_alpha_artifacts.py`

## AG03-11 - Prompt unit tests (snapshot) + CI

Fixtures:

- `tests/fixtures/prompts/context.json`
- `tests/fixtures/prompts/*.output.json`

Test:

- `tests/test_ag03_prompt_snapshots.py`

Valida:

- schema de salida de prompt.
- no invención de `test_id`, tablas o columnas.
- citas KB válidas en nodos que deben citar.

## AG03-13 - Tests unitarios del requisito

Suite específica AG03:

```bash
python3 -m pytest -q \
  tests/test_ag03_alpha_loop_integration.py \
  tests/test_ag03_alpha_artifacts.py \
  tests/test_ag03_prompt_snapshots.py
```

Cobertura:

- integración de `alpha_loop` en nodos LLM del grafo.
- persistencia de artefactos por iteración y registro en `persist_node`.
- snapshots de prompts con validación de schema, no invención y citas KB.

## AG03-14 - Documentación actualizada

Documentación operativa del workflow y verificación:

- `README.md` (sección AG03 + comando de verificación)
- `docs/how_to_run.md` (comandos AG03 y rutas de evidencias)
- `docs/alphacodium_workflow.md`
- `docs/ag03_iteraciones_reales.md`

## AG03-15 - Verificación y evidencias

Evidencia local de aceptación:

- `run_results/ag03-15-check/pytest_ag03.log`
- `run_results/ag03-15-check/verification_summary.json`

Nota traza LangSmith:

- en este entorno la traza externa no está configurada; se deja `langsmith_trace_link = N/A`.

## Registro explícito AG03-06 y AG03-07

AG03-06 (registro de evidencias de iteración):

- Definido en sección `Registro de evidencias de iteración (AG03-06)`.
- Implementado por `alpha_loop(...)` escribiendo:
  - `prompt.md`
  - `output.json`
  - `validation.json`
  - `fix.diff` (si aplica)
  - `iterations_manifest.jsonl`

AG03-07 (estándar Plan->Draft->Validate->Repair):

- Definido en sección `AlphaCodium Loop estándar (AG03-07)`.
- Implementado en `src/erp_fraud/agents/alpha_loop.py`.
- Integrado en nodos LLM del grafo vía `src/erp_fraud/graph/nodes/planning.py`, `src/erp_fraud/graph/nodes/explainer.py` y `src/erp_fraud/graph/nodes/scoring.py`.
