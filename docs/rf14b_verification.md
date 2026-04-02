# RF14b Verification Evidence

Fecha de verificación: **2026-04-02**.

## Alcance verificado

- RF14b-11: tests de integración del requisito RF14b
- RF14b-12: documentación actualizada (README + docs/runbook)
- RF14b-13: verificación ejecutada y evidencia guardada

## Comandos ejecutados

```bash
python3 -m pytest -q \
  tests/test_rf14b_contracts.py \
  tests/test_rf14b_env_validation.py \
  tests/test_rf14b_evaluators.py \
  tests/test_rf14b_langsmith_dataset.py \
  tests/test_rf14b_experiments_script.py
```

Resultado:

- `13 passed in 10.63s`

Ejecución de experimentos RF14b-08 para evidencia:

```bash
python3 scripts/run_rf14b_experiments.py --run-id-prefix rf14b-13-check
```

Resultado:

- `status: OK`
- artefactos:
  - `run_results/rf14b-13-check-rf14b08/rf14b_experiments.json`
  - `run_results/rf14b-13-check-rf14b08/rf14b_experiments.md`

Validación de esquema/config:

```bash
python3 scripts/validate_project_schema.py
```

Resultado:

- `OK schema/config validation`

Gate pre-LangSmith:

```bash
python3 scripts/run_pre_langsmith_gate.py
```

Resultado:

- `OK: pre-langsmith gate PASSED`
- artefacto: `run_results/pre_langsmith_gate.json`

## Evidencia consolidada

- `run_results/rf14b-13-check/verification_summary.json`

## Notas

- LangSmith cloud sigue siendo opcional para este cierre; RF14b queda validado con trazabilidad local + artefactos reproducibles.
- La ejecución del script puede imprimir warnings de PyArrow/CPU en macOS sandboxed (`sysctlbyname`), sin impacto funcional.

## Checklist “Listos Para Cloud”

Se considera preparado para paso a cloud cuando se cumpla:

1. 3 runs reales consecutivos `llm_mode=real` con el mismo dataset y `graph_status=OK`.
2. Guardrails sin alucinaciones críticas (sin columnas/test_ids inventados).
3. Coste y latencia medidos por nodo en `run_metadata.llm_runtime_by_node`.
4. Playbook de errores actualizado y probado (`docs/langsmith_tracing_runbook.md`).

Comprobación automática (cuando tengas 3 run_ids reales):

```bash
python3 scripts/check_real_cloud_readiness.py \
  --base-dir run_results \
  --run-ids <run_id_1> <run_id_2> <run_id_3> \
  --output run_results/cloud_readiness_check.json
```

Inspección funcional de un run real (para demo/presentación):

```bash
python3 scripts/show_run_summary.py --run-id <run_id_real>
```

Interpretación rápida:

1. `Hypotheses`: qué hipótesis construyó el planner.
2. `Selected Tests`: qué tests de catálogo aplicó a cada hipótesis.
3. `Findings`: dónde detectó señales de riesgo.
4. `Score`: tipología de fraude final (`final_label`) y confianza.
5. `Explanations`: narrativa de evidencia por entidad.
6. `LLM Runtime`: si cada nodo fue `OK` real o cayó en fallback.
