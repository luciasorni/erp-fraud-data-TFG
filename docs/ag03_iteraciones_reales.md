# AG03-12 - Evidencias Reales de Iteraciones AlphaCodium

Este documento registra iteraciones **reales** (no simuladas en texto) del loop:

`prompt -> output -> validación -> fix (si aplica) -> resultado`

Objetivo de defensa: mostrar que el sistema no acepta salidas LLM sin validación y deja trazabilidad completa por nodo.

## Caso 1: `hypothesis_planner` con reparación (2 iteraciones)

Run real: `ag03-08-check`

Artefactos:
- `run_results/ag03-08-check/alphacodium/hypothesis_planner/iteration_001/prompt.md`
- `run_results/ag03-08-check/alphacodium/hypothesis_planner/iteration_001/output.json`
- `run_results/ag03-08-check/alphacodium/hypothesis_planner/iteration_001/validation.json`
- `run_results/ag03-08-check/alphacodium/hypothesis_planner/iteration_001/fix.diff`
- `run_results/ag03-08-check/alphacodium/hypothesis_planner/iteration_002/prompt.md`
- `run_results/ag03-08-check/alphacodium/hypothesis_planner/iteration_002/output.json`
- `run_results/ag03-08-check/alphacodium/hypothesis_planner/iteration_002/validation.json`
- `run_results/ag03-08-check/alphacodium/hypothesis_planner/iterations_manifest.jsonl`

Resumen:
- `iteration=1`: `status=REPAIR`, `validation_passed=false`, error de validación (`value must be good`).
- `iteration=2`: `status=OK`, `validation_passed=true`, sin errores.

Interpretación:
- El loop detecta fallo de esquema en la primera salida y obliga reparación antes de aceptar resultado.

## Caso 2: `test_planner` en primera pasada (1 iteración)

Run real: `rf14-06-select`

Artefactos:
- `run_results/rf14-06-select/alphacodium/test_planner/iteration_001/prompt.md`
- `run_results/rf14-06-select/alphacodium/test_planner/iteration_001/output.json`
- `run_results/rf14-06-select/alphacodium/test_planner/iteration_001/validation.json`
- `run_results/rf14-06-select/alphacodium/test_planner/iterations_manifest.jsonl`

Resumen:
- `iteration=1`: `status=OK`, `validation_passed=true`.

Interpretación:
- La propuesta de tests se aceptó en primer intento porque ya cumplía allowlist y esquema.

## Caso 3: `expert_explainer` con guardrails (1 iteración)

Run real: `rf14-08-ok`

Artefactos:
- `run_results/rf14-08-ok/alphacodium/expert_explainer/iteration_001/prompt.md`
- `run_results/rf14-08-ok/alphacodium/expert_explainer/iteration_001/output.json`
- `run_results/rf14-08-ok/alphacodium/expert_explainer/iteration_001/validation.json`
- `run_results/rf14-08-ok/alphacodium/expert_explainer/iterations_manifest.jsonl`

Resumen:
- `iteration=1`: `status=OK`, `validation_passed=true`.

Interpretación:
- La explicación solo se acepta si respeta guardrails sobre evidencia real (`test_id` y columnas existentes).

## Evidencia técnica complementaria

Tests AG03 ejecutados para soportar estas evidencias:

```bash
python3 -m pytest -q \
  tests/test_ag03_alpha_loop_integration.py \
  tests/test_ag03_alpha_artifacts.py \
  tests/test_ag03_prompt_snapshots.py
```

Cobertura que aporta cada test:
- `tests/test_ag03_alpha_loop_integration.py`: comprueba integración de `alpha_loop` en nodos LLM.
- `tests/test_ag03_alpha_artifacts.py`: valida artefactos por iteración y su registro en `persist_node`.
- `tests/test_ag03_prompt_snapshots.py`: valida snapshots de prompts (schema, no invención, citas KB).

