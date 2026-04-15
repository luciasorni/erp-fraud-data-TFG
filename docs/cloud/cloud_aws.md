# Cloud AWS — Cierre Consolidado RF14c

Este documento consolida la operación cloud de RF14c y referencia la evidencia real ya validada.

## 1) Arquitectura final RF14c

- Runner del proyecto con `RUN_MODE=local|cloud`.
- En `RUN_MODE=cloud`:
  - descarga inputs desde S3,
  - calcula `artifact_hash`,
  - lee/escribe state store (`last_artifact_hash.json` por `PROCESS_SCOPE`),
  - ejecuta pipeline local dentro de workspace temporal,
  - sube outputs a `runs/<run_id>/`.
- Triggering soportado:
  - manual (`ecs run-task`),
  - programado (`EventBridge Scheduler`),
  - automático por evento de artefactos S3 (`S3 -> EventBridge -> Lambda -> ECS`).

## 2) Naming usado (real)

- Región: `eu-west-1`
- Bucket S3: `tfg-fraud-dev-euw1-lucia01`
- ECS Cluster: `tfg-fraud-dev-ecs-cluster`
- ECS Task Definition family: `tfg-fraud-dev-task`
- ECR repo: `tfg-fraud-dev-ecr-pipeline`
- ECS log group: `/ecs/tfg-fraud-dev-pipeline`
- Lambda RF14c-23: `tfg-fraud-dev-rf14c23-trigger`

## 3) Recursos AWS creados

- S3 (inputs/artifacts/runs/state)
- ECR (imagen pipeline)
- ECS Fargate (ejecución batch)
- IAM roles (task execution, task role, scheduler/lambda invocación)
- CloudWatch Logs
- EventBridge Scheduler (RF14c-22)
- EventBridge Rule + Lambda (RF14c-23)

## 4) Scopes soportados

- `PROCESS_SCOPE=p2p`
- `PROCESS_SCOPE=o2c`
- `PROCESS_SCOPE=both`

Estado validado:
- RF14c-20: p2p manual OK
- RF14c-21: o2c y both manual OK
- RF14c-22: scheduler OK
- RF14c-23: trigger automático con comparación de `artifact_hash` OK

## 5) Flujo manual cloud (operación)

1. Publicar imagen en ECR.
2. Registrar nueva revisión de task definition.
3. Lanzar task con overrides:
   - `RUN_MODE=cloud`
   - `PROCESS_SCOPE=<p2p|o2c|both>`
4. Esperar `tasks-stopped`.
5. Verificar `exitCode`, logs y artefactos en S3.

### Modos de pipeline en `run`

- `--pipeline-mode deterministic` (default): genera artefactos mínimos (`report.*`, `ranking.*`, `run_metadata.json`, etc.).
- `--pipeline-mode graph`: tras el pipeline base ejecuta `run_graph_full(...)` y persiste también `graph/*` (incluyendo `second_level_analysis.*` cuando aplica).

`--process-family` debe informarse explícitamente para evitar ambigüedad:
- `--process-family p2p`
- `--process-family o2c`

Nota: `PROCESS_SCOPE=both` se usa para alcance de artefactos/hash/state; no existe `process_family=both` en el grafo actual.

## 6) Flujo scheduler (RF14c-22)

- Scheduler lanza `ecs:RunTask` periódico contra `tfg-fraud-dev-task`.
- El run se ejecuta en cloud y genera nuevo `runs/<run_id>/`.
- Se actualiza `state/<scope>/last_artifact_hash.json` en éxito.

Referencia de evidencia: `docs/cloud/RF14c_22_eventbridge_scheduler.md`.

## 7) Flujo trigger automático (RF14c-23)

- Evento de cambio en S3 (`artifacts/prompts|catalogs|mappings`) llega a EventBridge.
- EventBridge invoca Lambda `tfg-fraud-dev-rf14c23-trigger`.
- Lambda:
  - recalcula `artifact_hash` observado,
  - compara con state previo del scope,
  - si cambia => `ecs.run_task`,
  - si no cambia => skip.

Código: `lambda/rf14c23/lambda_function.py`  
Evidencia: `docs/cloud/RF14c_23_trigger_automatico_s3_eventbridge_ecs.md`.

## 8) Layout S3 operativo

- Inputs:
  - `inputs/datasets/<scope>/`
  - `inputs/docs/shared/`
  - `inputs/docs/<scope>/`
- Artefactos:
  - `artifacts/prompts/shared/`
  - `artifacts/catalogs/<scope>/`
  - `artifacts/mappings/<scope>/`
  - `artifacts/mappings/shared/` (fallbacks comunes)
- Outputs:
  - `runs/<run_id>/...`
- State:
  - `state/p2p/last_artifact_hash.json`
  - `state/o2c/last_artifact_hash.json`
  - `state/both/last_artifact_hash.json`

## 9) Verificación de outputs

### Artefactos del run

```bash
aws s3 ls s3://tfg-fraud-dev-euw1-lucia01/runs/<RUN_ID>/ --recursive --profile tfg-fraud-dev
```

Mínimos esperados:
- `run_metadata.json`
- `schema_summary.json`
- `report.json`
- `ranking.json`

Cuando se ejecuta con `--pipeline-mode graph`, además deben aparecer en S3:
- `graph/graph_state.json`
- `graph/hypotheses.json`
- `graph/selected_tests.json`
- `graph/findings.json`
- `graph/scores.json`
- `graph/manifest.json`

Opcionales en modo graph:
- `graph/explanations.json`
- `graph/explanations.md`
- `graph/second_level_analysis.json`
- `graph/second_level_analysis.md`

### State store

```bash
aws s3 cp s3://tfg-fraud-dev-euw1-lucia01/state/<SCOPE>/last_artifact_hash.json - --profile tfg-fraud-dev
```

## 10) Logs relevantes

### Últimos streams ECS

```bash
aws logs describe-log-streams \
  --log-group-name /ecs/tfg-fraud-dev-pipeline \
  --region eu-west-1 \
  --profile tfg-fraud-dev \
  --order-by LastEventTime \
  --descending \
  --max-items 10
```

### Eventos de un stream concreto

```bash
aws logs get-log-events \
  --log-group-name /ecs/tfg-fraud-dev-pipeline \
  --log-stream-name '<STREAM>' \
  --region eu-west-1 \
  --profile tfg-fraud-dev \
  --limit 200
```

## 11) Rehacer imagen / push / task definition

Resumen operativo:
1. `docker build`
2. login ECR
3. tag/push (`<sha>` y opcional `latest`)
4. `describe-task-definition` + patch de `image`
5. `register-task-definition`
6. `run-task`

Automatización CI para publish en main: ver `docs/cloud/github_actions_ecr.md` y `.github/workflows/ecr-publish-main.yml`.

## 12) Probar scheduler y trigger automático

- Scheduler:
  - validar schedule habilitado,
  - confirmar task lanzada con `startedBy=chronos-schedule/...`,
  - verificar nuevo run en S3.
- Trigger automático:
  - subir cambio real en `artifacts/*`,
  - validar invocación Lambda,
  - validar decisión hash (`skip/launch`),
  - si launch: validar task ECS + outputs.

## 13) Limitaciones conocidas

- Tests de `pytest` para RF14c usan mocks/fakes (no integran contra AWS real en CI).
- La validación AWS real depende de credenciales, recursos y secretos fuera del repo.
- Las evidencias de consola/JSON se mantienen en docs y `docs/cloud/evidences/`.
- El enlace final de LangSmith debe registrarse manualmente por run final si no está persistido en evidencias del repo.

## 14) Referencias

- `docs/cloud/rf14c_20_ejecucion_cloud_p2p.md`
- `docs/cloud/rf14c_21_ejecucion_cloud_o2c_both.md`
- `docs/cloud/RF14c_22_eventbridge_scheduler.md`
- `docs/cloud/RF14c_23_trigger_automatico_s3_eventbridge_ecs.md`
- `docs/cloud/rf14c_final_verification.md`
- `docs/cloud/troubleshooting.md`
