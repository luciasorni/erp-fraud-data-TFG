# RF14c — Verificación Final de Criterios de Aceptación

Este documento consolida el cierre de RF14c usando evidencias reales ya obtenidas.

## Criterios de aceptación y evidencia

| Criterio | Estado | Evidencia principal | Qué demuestra |
|---|---|---|---|
| RF14c-20: ejecución cloud manual p2p en ECS | OK | `docs/cloud/rf14c_20_ejecucion_cloud_p2p.md` | Task ECS con `exitCode=0`, outputs en `runs/` y state p2p actualizado |
| RF14c-21: ejecución cloud manual o2c y both | OK | `docs/cloud/rf14c_21_ejecucion_cloud_o2c_both.md` + `docs/cloud/evidences/rf14c21_*` | Soporte multi-scope real (`o2c`, `both`) con persistencia de artefactos y state por scope |
| RF14c-22: re-ejecución programada | OK | `docs/cloud/RF14c_22_eventbridge_scheduler.md` | Scheduler activo y lanzamiento automático de ECS con resultado exitoso |
| RF14c-23: trigger automático por cambio en artefactos | OK | `docs/cloud/RF14c_23_trigger_automatico_s3_eventbridge_ecs.md` + `docs/cloud/evidences/rf14c23_*` | Flujo S3/EventBridge/Lambda/ECS operativo con control por `artifact_hash` |

## Recursos AWS observados (reales)

- Bucket S3: `tfg-fraud-dev-euw1-lucia01`
- ECS Cluster: `tfg-fraud-dev-ecs-cluster`
- Task definition family: `tfg-fraud-dev-task`
- ECR repo: `tfg-fraud-dev-ecr-pipeline`
- Log group: `/ecs/tfg-fraud-dev-pipeline`
- Lambda trigger: `tfg-fraud-dev-rf14c23-trigger`

## Comandos de verificación usados (resumen)

```bash
aws ecs run-task ...
aws ecs wait tasks-stopped ...
aws ecs describe-tasks ...
aws logs describe-log-streams ...
aws logs get-log-events ...
aws s3 ls s3://tfg-fraud-dev-euw1-lucia01/runs/<run_id>/ --recursive --profile tfg-fraud-dev
aws s3 cp s3://tfg-fraud-dev-euw1-lucia01/state/<scope>/last_artifact_hash.json - --profile tfg-fraud-dev
```

## Evidencias auxiliares integradas

- `docs/cloud/evidences/rf14c21_o2c_describe_tasks.json`
- `docs/cloud/evidences/rf14c21_o2c_s3_listing.txt`
- `docs/cloud/evidences/rf14c21_o2c_state_last_artifact_hash.json`
- `docs/cloud/evidences/rf14c21_both_describe_tasks.json`
- `docs/cloud/evidences/rf14c21_both_s3_listing.txt`
- `docs/cloud/evidences/rf14c21_both_state_last_artifact_hash.json`
- `docs/cloud/evidences/rf14c23_describe_tasks.json`
- `docs/cloud/evidences/rf14c23_runs_listing.txt`
- `docs/cloud/evidences/rf14c23_state_both_last_artifact_hash.json`

## Checklist final de aceptación

- [x] Runner cloud estable para `p2p`.
- [x] Runner cloud estable para `o2c`.
- [x] Runner cloud estable para `both`.
- [x] Outputs mínimos obligatorios en runs cloud.
- [x] State store actualizado en éxito.
- [x] Scheduler operativo (RF14c-22).
- [x] Trigger automático S3/EventBridge/Lambda/ECS operativo (RF14c-23).
- [x] Cobertura de tests RF14c documentada en `docs/integration_tests_registry.md`.

## LangSmith (nota honesta)

- Enlace final único de LangSmith para “cierre RF14c completo”: **pendiente de inserción manual** cuando se elija el run de referencia final.
- Este documento no inventa enlace si no está persistido en evidencia del repo.

## Conclusión

Con las evidencias enlazadas, RF14c queda verificado end-to-end en AWS para ejecución manual, programada y automática por evento, con scopes `p2p`, `o2c` y `both`.
