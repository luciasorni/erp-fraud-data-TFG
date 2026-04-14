# RF14c-12 — Outputs mínimos obligatorios por run

## Objetivo
Definir y validar los artefactos mínimos que debe generar cada ejecución cloud en:

```text
runs/<run_id>/
```

## Outputs obligatorios (siempre)
- `run_metadata.json`
- `schema_summary.json`
- `report.json`
- `ranking.json`

## Outputs obligatorios cuando grafo está activo
- `graph/graph_state.json`
- `graph/hypotheses.json`
- `graph/selected_tests.json`
- `graph/findings.json`
- `graph/scores.json`

## Outputs opcionales (no bloquean)
- `graph/explanations.json`
- `graph/explanations.md`
- `graph/second_level_analysis.json`
- `graph/second_level_analysis.md`

## Validación de contenido mínimo en run_metadata.json
Además de existir el fichero, se exige:
- `run_id`
- `process_scope`
- `artifact_hash`

## Implementación realizada (RF14c-12)
- Capa reusable: `src/erp_fraud/storage/run_outputs.py`
  - `get_required_run_outputs(...)`
  - `validate_required_run_outputs(...)`
- Integración natural en pipeline:
  - `src/erp_fraud/cli/main.py` (ramas local p2p y o2c) justo después de consolidar outputs.

Comportamiento:
- si falta obligatorio -> error controlado y exit code no cero.
- si falta opcional -> no falla.
