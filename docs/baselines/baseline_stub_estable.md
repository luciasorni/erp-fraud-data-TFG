# Baseline Stub Estable

## Identificación

- `baseline_name`: `baseline-stub-estable`
- `run_id`: `baseline-stub-estable-20260402`
- `base_commit`: `c770f52`
- `dataset_hash`: `7cab17f42672c3b452f607902e7163e0c3b5a648aa69be470bf29524f94d6dc7`
- `timestamp_utc`: `2026-04-02T08:03:53+00:00`

## Comando usado

```bash
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --run-id baseline-stub-estable-20260402
```

## Artefactos de referencia (local)

En `run_results/baseline-stub-estable-20260402/`:

- `run_metadata.json`
- `schema_summary.json`
- `data_validation_report.json`
- `test_runs.json`
- `ranking.json`
- `report.json`
- `report.md`
- `report.html`

## Uso

Este baseline se usa para comparar cuando activemos `llm_mode=real`:

- diferencias de `selected_tests`
- diferencias en `findings` y `ranking`
- diferencias en `fraud_type_predicho` y reporte final
