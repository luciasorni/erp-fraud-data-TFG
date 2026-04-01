# RF14b-10 — Runbook de Trazas (Local + Cloud)

Este runbook explica cómo reproducir trazas del grafo y experimentos en entorno local y en cloud.

## 1) Variables mínimas

Obligatorias para publicar trazas en LangSmith:

- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`

Recomendadas:

- `LANGSMITH_TRACING=true`
- `LANGCHAIN_TRACING_V2=true`
- `LANGSMITH_ENDPOINT=https://api.smith.langchain.com` (o endpoint EU)

Validación:

```bash
python3 scripts/validate_required_env.py --profile langsmith
```

## 2) Ejecución local (pipeline grafo)

### 2.1 Run estándar

```bash
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --run-id rf14b-local
```

### 2.2 Experimentos de modelos (RF14b-08)

```bash
python3 scripts/run_rf14b_experiments.py \
  --run-id-prefix rf14b-local-exp \
  --models-config config/models.yaml \
  --planner-baseline-model gpt-5.4-mini \
  --planner-candidate-model gpt-5.4 \
  --scoring-baseline-profile default \
  --scoring-candidate-profile conservative
```

## 3) Qué revisar en outputs locales

En `run_results/<run_id>/`:

- `graph/manifest.json`
- `graph/report.json` (si aplica)
- `graph/score_compare.json` (si se comparan perfiles)
- `graph/score_experiment.json` (estado READY/SKIPPED para experimento)
- `graph/langsmith_eval_dataset.jsonl` (RF14b-07)

En `run_metadata`:

- `langsmith` (snapshot de entorno)
- `node_trace_events` (traza local por nodo)
- `rf14b_evaluation`
- `langsmith_eval_dataset`

## 4) Publicación de dataset (opcional)

Para intentar publicación en LangSmith del dataset de evaluación:

- activar `enable_langsmith_dataset_publish=true` en `run_metadata` (vía flujo/script)

Resultado esperado:

- `run_metadata["langsmith_eval_dataset"]["publish"]` con estado de publicación.

## 5) Ejecución cloud (patrón recomendado)

La integración cloud final se cubre en RF14c, pero para trazas RF14b el patrón es:

1. Inyectar variables LangSmith como secretos/variables del job.
2. Ejecutar el mismo comando de run/experimentos en el contenedor.
3. Persistir `run_results/` en almacenamiento compartido (S3 u otro).
4. Revisar trazas en LangSmith por `LANGSMITH_PROJECT`.

Variables a inyectar en cloud:

- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `LANGSMITH_TRACING`
- `LANGCHAIN_TRACING_V2`
- `LANGSMITH_ENDPOINT`

## 6) Troubleshooting rápido

1. `LANGSMITH_API_KEY` ausente:
- `validate_required_env.py --profile langsmith` falla.
- Solución: definir API key en `.env`/secret manager.

2. Trazas no aparecen pero run local OK:
- `LANGSMITH_TRACING`/`LANGCHAIN_TRACING_V2` desactivados.
- Solución: activar ambos a `true` y re-ejecutar.

3. `score_experiment` en `SKIPPED`:
- revisar `enable_langsmith_experiments` y snapshot `langsmith` en metadata.

4. Dataset no publicado:
- validar `enable_langsmith_dataset_publish` y credenciales válidas.

## 7) Checklist operativo mínimo

- `python3 scripts/validate_required_env.py --profile langsmith` en verde
- run del grafo completado
- `run_metadata.langsmith` presente
- `run_metadata.node_trace_events` presente
- artefactos de experimento generados (`rf14b_experiments.json/md`)
