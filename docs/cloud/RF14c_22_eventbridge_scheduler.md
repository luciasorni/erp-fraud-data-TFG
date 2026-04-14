# RF14c-22 — Evidencia de re-ejecución programada con EventBridge Scheduler

> Documento consolidado RF14c: `docs/cloud/cloud_aws.md`  
> Cierre final de aceptación: `docs/cloud/rf14c_final_verification.md`

## Objetivo
Validar que la infraestructura cloud del proyecto permite lanzar re-ejecuciones automáticas del pipeline mediante **Amazon EventBridge Scheduler**, invocando una task ECS Fargate ya validada previamente.

En esta fase se busca demostrar que:

- existe una programación activa en AWS,
- dicha programación lanza automáticamente una task ECS,
- la task ejecuta el pipeline en modo cloud,
- se generan artefactos nuevos en S3,
- y se actualiza correctamente el state store.

---

## Configuración funcional de la programación

### Nombre de la programación
- `tfg-fraud-dev-sched-p2p-daily`

### Descripción
- `Daily scheduled ECS run for TFG fraud pipeline p2p`

### Grupo
- `default`

### Zona horaria
- `Europe/Madrid`

### Tipo
- recurrente

### Expresión
- `rate(1 day)`

### Intervalo flexible
- desactivado

### Estado
- habilitado

### Rol de ejecución
- `tfg-fraud-dev-scheduler-ecs-role`

### Acción al finalizar
- `NONE`

### Reintentos
- desactivados

### DLQ
- ninguna

### Cifrado
- por defecto (`aws/scheduler`)

---

## Destino configurado

### Servicio destino
- Amazon ECS

### API invocada
- `RunTask`

### Cluster ECS
- `tfg-fraud-dev-ecs-cluster`

### Task definition
- `tfg-fraud-dev-task`

### Tipo de lanzamiento
- `FARGATE`

### Overrides configurados
```json
{
  "containerOverrides": [
    {
      "name": "erp-fraud-pipeline",
      "command": ["run", "--input-zip", "erp_fraud_data.zip"],
      "environment": [
        { "name": "RUN_MODE", "value": "cloud" },
        { "name": "PROCESS_SCOPE", "value": "p2p" }
      ]
    }
  ]
}
```

### Network configuration usada
- subnets:
  - `subnet-091fb9bd171d238aa`
  - `subnet-00cd0a8035d8f7dd6`
  - `subnet-0329d6462aeb6fdf7`
- security group:
  - `sg-0bbcc120180a92672`

---

## Evidencia de lanzamiento automático

### Task detectada en el cluster
```text
arn:aws:ecs:eu-west-1:798350130349:task/tfg-fraud-dev-ecs-cluster/66fd820689e44067b24be48535cc4326
```

### Evidencia clave de que la lanzó el scheduler
En la salida de `describe-tasks` aparece:

```text
"startedBy": "chronos-schedule/tfg-fraud-dev-sched"
```

Esto demuestra que la task no fue lanzada manualmente, sino por una programación automática de EventBridge Scheduler.

---

## Resultado de la task programada

### Datos relevantes de `describe-tasks`
- `lastStatus = STOPPED`
- `launchType = FARGATE`
- `platformVersion = 1.4.0`
- `exitCode = 0`
- `taskDefinitionArn = arn:aws:ecs:eu-west-1:798350130349:task-definition/tfg-fraud-dev-task:6`

### Overrides realmente aplicados
```json
{
  "containerOverrides": [
    {
      "name": "erp-fraud-pipeline",
      "command": [
        "run",
        "--input-zip",
        "erp_fraud_data.zip"
      ],
      "environment": [
        {
          "name": "RUN_MODE",
          "value": "cloud"
        },
        {
          "name": "PROCESS_SCOPE",
          "value": "p2p"
        }
      ]
    }
  ]
}
```

### Interpretación
La tarea programada:
- usó la task definition correcta,
- aplicó los overrides esperados,
- ejecutó el pipeline en modo cloud,
- y finalizó con éxito (`exitCode = 0`).

---

## Evidencia de nuevo run en S3

### Nuevo run detectado
```text
runs/run-20260414-171548/
```

### Artefactos generados
```text
2026-04-14 19:16:15          3 runs/run-20260414-171548/data_dictionary.json
2026-04-14 19:16:15         48 runs/run-20260414-171548/data_dictionary.md
2026-04-14 19:16:15       1706 runs/run-20260414-171548/data_validation_report.json
2026-04-14 19:16:15       2827 runs/run-20260414-171548/ingest_logs.jsonl
2026-04-14 19:16:15         53 runs/run-20260414-171548/ranking.json
2026-04-14 19:16:15        598 runs/run-20260414-171548/ranking.parquet
2026-04-14 19:16:15       3687 runs/run-20260414-171548/report.html
2026-04-14 19:16:15      23610 runs/run-20260414-171548/report.json
2026-04-14 19:16:15       2636 runs/run-20260414-171548/report.md
2026-04-14 19:16:15        467 runs/run-20260414-171548/run_metadata.json
2026-04-14 19:16:16       1301 runs/run-20260414-171548/run_structure.json
2026-04-14 19:16:16      76259 runs/run-20260414-171548/schema_summary.json
2026-04-14 19:16:16        108 runs/run-20260414-171548/test_runs.json
```

### Interpretación
La programación generó un **run nuevo**, distinto de los manuales anteriores, lo que valida la ejecución automatizada end-to-end.

---

## Evidencia de actualización del state store

### Contenido obtenido
```json
{"last_artifact_hash":"f55c543e44549668f0e9412e643a94dc49978f3e634b2a293e94d1a1d93722ac","last_run_id":"run-20260414-171548","process_scope":"p2p","updated_at":"2026-04-14T17:16:15+00:00"}
```

### Interpretación
El state store de `p2p` se actualizó correctamente con:
- el `artifact_hash`,
- el nuevo `last_run_id`,
- el `process_scope`,
- y el timestamp de actualización.

---

## Conclusión

La evidencia obtenida demuestra que la programación automática mediante **EventBridge Scheduler** funciona correctamente sobre la arquitectura cloud desplegada.

### RF14c-22 se considera cumplido porque:
1. se creó una programación recurrente válida,
2. la programación lanzó automáticamente una task ECS Fargate,
3. la task fue ejecutada con los overrides esperados (`RUN_MODE=cloud`, `PROCESS_SCOPE=p2p`),
4. el contenedor terminó con `exitCode = 0`,
5. se generó un nuevo run en S3,
6. se actualizó el state store de `p2p`.

---

## Encaje dentro de RF14c

Con esta validación, queda demostrada la cadena completa:

- **RF14c-20**: ejecución manual cloud `p2p`
- **RF14c-21**: ejecución manual cloud `o2c` y `both`
- **RF14c-22**: re-ejecución automática programada con EventBridge Scheduler

Esto confirma que la productivización mínima en AWS está operativa tanto en modo manual como en modo programado.

---

## Evidencia mínima a conservar
Se recomienda conservar como prueba:

- salida de `aws ecs list-tasks`
- salida de `aws ecs describe-tasks` de la task lanzada por scheduler
- listado S3 del nuevo run `runs/run-20260414-171548/`
- contenido de `state/p2p/last_artifact_hash.json`
- captura de la programación creada en EventBridge Scheduler
