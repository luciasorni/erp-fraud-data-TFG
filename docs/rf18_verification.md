# RF18 — Verificación

## Tareas cerradas en este bloque

- `RF18-11`: tests unitarios/integración de scoring actualizados.
- `RF18-12`: documentación de uso y operación actualizada (`README`, `docs/how_to_run.md`, `docs/scoring.md`).
- `RF18-13`: ejecución de verificación y guardado de evidencia en `run_results/rf18-13-check/`.

## Suite ejecutada (RF18)

```bash
python3 -m pytest -q \
  tests/test_rf18_score_schema.py \
  tests/test_rf18_scoring_prompt.py \
  tests/test_rf18_scoring_agent.py \
  tests/test_rf18_scoring_end_to_end.py \
  tests/test_rf15c_scoring_node.py \
  tests/test_rf15c_persist_node.py
```

## Evidencia

- `run_results/rf18-13-check/pytest_rf18.stdout.log`
- `run_results/rf18-13-check/pytest_rf18.stderr.log`
- `run_results/rf18-13-check/rf18_13_acceptance_verification_report.json`

## Nota LangSmith

- Integración RF18-09 está en modo opcional/no bloqueante.
- Si LangSmith no está configurado, el estado esperado es `SKIPPED`.
- En este entorno, el `trace_link` puede quedar en `N/A`.
