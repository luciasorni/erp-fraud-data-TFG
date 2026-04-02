# RF14b-09 — Informe de Experimentos (LangSmith-ready)

Este documento recoge la evidencia de RF14b-08: dos experimentos comparativos (planner y scoring) ejecutados de forma reproducible.

## Objetivo

Comparar outputs al variar configuración de modelo en dos partes del grafo:

1. `hypothesis_planner` + `test_planner`
2. `scoring` (perfiles baseline/candidate)

## Comando ejecutado

```bash
python3 scripts/run_rf14b_experiments.py \
  --run-id-prefix rf14b-08-doc-check \
  --models-config config/models.yaml \
  --planner-baseline-model gpt-5.4-mini \
  --planner-candidate-model gpt-5.4 \
  --scoring-baseline-profile default \
  --scoring-candidate-profile conservative
```

## Artefactos generados

- `run_results/rf14b-08-doc-check-rf14b08/rf14b_experiments.json`
- `run_results/rf14b-08-doc-check-rf14b08/rf14b_experiments.md`

## Resultado resumido

### Experimento 1: Planner

- baseline model: `gpt-5.4-mini`
- candidate model: `gpt-5.4`
- `selected_tests_changed`: `false`
- `hypothesis_ids_changed`: `false`

Interpretación:
- Con el input actual, el planificador se comporta estable entre ambos modelos.

### Experimento 2: Scoring

- baseline profile: `default` (`scoring-deterministic-v2`)
- candidate profile: `conservative` (`scoring-deterministic-conservative-v1`)
- `scoring_compare_status`: `OK`
- `final_label_changed`: `false`
- `confidence_delta`: `0.0`

Interpretación:
- Con el fixture actual no hay diferencia material de etiqueta/confianza entre perfiles.

## Conclusiones

1. La comparativa de modelos queda implementada y trazada en artefactos versionables.
2. La infraestructura está lista para ejecutar este mismo flujo con datasets más exigentes y observar cambios reales.
3. RF14b-09 queda cubierto a nivel de informe reproducible; RF14b-10 puede centrarse en guía operativa local/cloud.

## Notas

- El script no bloquea por LangSmith: produce evidencia local aunque no haya credenciales activas.
- Si `enable_langsmith_dataset_publish=true`, el run puede además publicar dataset de evaluación (RF14b-07).
