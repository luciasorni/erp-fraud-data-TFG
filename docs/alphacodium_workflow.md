# AG03 - Workflow AlphaCodium

## Objetivo

Definir una forma estándar de trabajar con AlphaCodium con aprobación humana:

1. AlphaCodium genera propuestas (prompts, código, tests, docs).
2. Validadores automáticos comprueban seguridad y consistencia.
3. Revisión humana decide integración.

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
4. `pytest` (suite objetivo RF03/RF04/RF07/RF08/RF15b)
