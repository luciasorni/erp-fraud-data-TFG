# Artefactos de ejecución

El sistema está diseñado alrededor de runs identificables. En local se escriben en `run_results/<run_id>/`; en cloud se suben a `runs/<run_id>/` dentro del bucket S3 configurado.

## Contrato actual de outputs

Implementación:

- `src/erp_fraud/storage/run_outputs.py`

Outputs base obligatorios cuando se valida el contrato actual:

- `run_metadata.json`
- `schema_summary.json`
- `report.json`
- `ranking.json`

Outputs obligatorios si graph está activo:

- `graph/graph_state.json`
- `graph/hypotheses.json`
- `graph/selected_tests.json`
- `graph/findings.json`
- `graph/scores.json`

Outputs opcionales:

- `graph/explanations.json`
- `graph/explanations.md`
- `graph/second_level_analysis.json`
- `graph/second_level_analysis.md`

## Estructura local típica

```text
run_results/<run_id>/
  run_metadata.json
  schema_summary.json
  data_validation_report.json
  ingest_logs.jsonl
  test_runner_logs.jsonl
  test_runs.json
  ranking.json
  ranking.parquet
  report.json
  report.md
  report.html
  run_structure.json
  tests_outputs/
    <test_id>/
      findings.jsonl
      findings.parquet
      sample_top20.json
  drilldowns/
  graph/
    graph_state.json
    hypotheses.json
    selected_tests.json
    findings.json
    scores.json
    explanations.json
    explanations.md
    manifest.json
    second_level_analysis.json
    second_level_analysis.md
```

No todos los runs tienen todos los artefactos. Los artefactos graph dependen de `--pipeline-mode graph` y el análisis de segundo nivel solo aparece cuando se ejecuta el nodo correspondiente.

## Productores principales

| Artefacto | Productor |
|---|---|
| `run_metadata.json` | `src/erp_fraud/storage/run_metadata.py` / CLI |
| `schema_summary.json` | `src/erp_fraud/storage/schema_summary.py` |
| `data_validation_report.json` | `src/erp_fraud/storage/data_validation_*` |
| `test_runs.json` | `src/erp_fraud/catalog/test_runner.py` |
| `tests_outputs/*` | `src/erp_fraud/catalog/result_writer.py` |
| `ranking.json`, `ranking.parquet` | `src/erp_fraud/catalog/ranking_writer.py` |
| `report.json` | `src/erp_fraud/storage/report_json.py` |
| `report.md`, `report.html` | `src/erp_fraud/storage/reporting.py` |
| `graph/*` | `src/erp_fraud/graph/nodes/persist.py` |
| `graph/second_level_analysis.*` | `src/erp_fraud/graph/nodes/second_level_explainer.py` |

## Uso posterior

- API/UI leen artefactos desde S3 mediante `app/api/services/results_service.py` y `app/api/services/runs_service.py`.
- Comparación de runs usa snapshots persistidos en `src/erp_fraud/storage/runs_comparison.py`.
- Drilldown usa claves y plantillas controladas, no SQL libre.
- Cloud valida outputs mínimos y sube resultados a S3.

## Evidencias versionadas

Los outputs locales de `run_results/` están ignorados por git y pueden no estar disponibles en un clon limpio. Las evidencias cloud versionadas están en:

- `docs/cloud/evidences/`
- `docs/cloud/rf14c_final_verification.md`
- `docs/cloud/cloud_aws.md`
