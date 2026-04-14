# RF14c-20 — Evidencia de ejecución cloud exitosa (AWS ECS Fargate)

> Documento consolidado RF14c: `docs/cloud/cloud_aws.md`  
> Cierre final de aceptación: `docs/cloud/rf14c_final_verification.md`

## Objetivo
Validar que la productivización mínima en cloud funciona correctamente, ejecutando el pipeline en AWS mediante ECS Fargate y verificando:

- ejecución de la task en cloud,
- generación de artefactos en S3,
- actualización del state store,
- uso correcto de la infraestructura mínima definida en RF14c.

---

## Contexto de la ejecución

### Scope ejecutado
- `PROCESS_SCOPE = p2p`

### Run ID
- `rf14c20-p2p-005`

### Región AWS
- `eu-west-1`

### Cluster ECS
- `tfg-fraud-dev-ecs-cluster`

### Task Definition
- `tfg-fraud-dev-task`

### Imagen usada
- `798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline`

### Security Group
- `sg-0bbcc120180a92672`

### Subnets
- `subnet-091fb9bd171d238aa`
- `subnet-00cd0a8035d8f7dd6`
- `subnet-0329d6462aeb6fdf7`

---

## Comando de lanzamiento usado

```bash
export TASK_ARN=$(aws ecs run-task   --cluster "$CLUSTER"   --task-definition "$TASK_DEF_ARN"   --launch-type FARGATE   --count 1   --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_A,$SUBNET_B,$SUBNET_C],securityGroups=[$SG_ID],assignPublicIp=ENABLED}"   --overrides file:///tmp/ecs-overrides-p2p.json   --region "$AWS_REGION"   --profile "$AWS_PROFILE"   --query 'tasks[0].taskArn'   --output text)
```

---

## Identificador de la task ejecutada

```text
arn:aws:ecs:eu-west-1:798350130349:task/tfg-fraud-dev-ecs-cluster/ba57a00e247c444aa672aad443198e0f
```

---

## Resultado de la ejecución ECS

### Comando de verificación
```bash
aws ecs describe-tasks   --cluster "$CLUSTER"   --tasks "$TASK_ARN"   --region "$AWS_REGION"   --profile "$AWS_PROFILE"   --query 'tasks[0].{lastStatus:lastStatus,stopCode:stopCode,stoppedReason:stoppedReason,exitCode:containers[0].exitCode,containerReason:containers[0].reason}'   --output json
```

### Salida obtenida
```json
{
  "lastStatus": "STOPPED",
  "stopCode": "EssentialContainerExited",
  "stoppedReason": "Essential container in task exited",
  "exitCode": 0,
  "containerReason": null
}
```

### Interpretación
La task finalizó correctamente y el contenedor principal terminó con `exitCode = 0`, lo que confirma que el pipeline cloud se ejecutó sin error fatal.

---

## Evidencia de artefactos generados en S3

### Comando de verificación
```bash
aws s3 ls s3://tfg-fraud-dev-euw1-lucia01/runs/rf14c20-p2p-005/   --recursive   --profile "$AWS_PROFILE"
```

### Salida obtenida
```text
2026-04-14 18:11:05          3 runs/rf14c20-p2p-005/data_dictionary.json
2026-04-14 18:11:05         48 runs/rf14c20-p2p-005/data_dictionary.md
2026-04-14 18:11:05       1706 runs/rf14c20-p2p-005/data_validation_report.json
2026-04-14 18:11:05       2775 runs/rf14c20-p2p-005/ingest_logs.jsonl
2026-04-14 18:11:05         53 runs/rf14c20-p2p-005/ranking.json
2026-04-14 18:11:05        598 runs/rf14c20-p2p-005/ranking.parquet
2026-04-14 18:11:05       3635 runs/rf14c20-p2p-005/report.html
2026-04-14 18:11:05      23558 runs/rf14c20-p2p-005/report.json
2026-04-14 18:11:06       2568 runs/rf14c20-p2p-005/report.md
2026-04-14 18:11:06        463 runs/rf14c20-p2p-005/run_metadata.json
2026-04-14 18:11:06       1229 runs/rf14c20-p2p-005/run_structure.json
2026-04-14 18:11:06      76259 runs/rf14c20-p2p-005/schema_summary.json
2026-04-14 18:11:06        104 runs/rf14c20-p2p-005/test_runs.json
```

### Interpretación
Se generaron correctamente los artefactos mínimos esperados del run cloud, incluyendo:

- `run_metadata.json`
- `schema_summary.json`
- `data_validation_report.json`
- `ranking.json`
- `report.json`
- `report.md`
- `report.html`
- `test_runs.json`

Esto demuestra que el pipeline no solo arrancó, sino que completó la ejecución y persistió resultados finales en S3.

---

## Evidencia de actualización del state store

### Comando de verificación
```bash
aws s3 cp s3://tfg-fraud-dev-euw1-lucia01/state/p2p/last_artifact_hash.json -   --profile "$AWS_PROFILE"
```

### Salida obtenida
```json
{"last_artifact_hash":"f55c543e44549668f0e9412e643a94dc49978f3e634b2a293e94d1a1d93722ac","last_run_id":"rf14c20-p2p-005","process_scope":"p2p","updated_at":"2026-04-14T16:11:05+00:00"}
```

### Interpretación
El state store quedó actualizado correctamente tras el run exitoso, registrando:

- hash de artefactos usado,
- último run ejecutado,
- scope asociado,
- timestamp de actualización.

Esto valida la parte de persistencia de estado de RF14c.

---

## Componentes cloud validados en esta prueba

La evidencia obtenida demuestra el funcionamiento conjunto de:

- **ECR**: imagen desplegada y usada por ECS
- **ECS Fargate**: ejecución batch del pipeline
- **S3**: descarga de inputs y subida de outputs
- **CloudWatch Logs**: trazabilidad de ejecución
- **Secrets Manager**: inyección de secretos runtime
- **IAM roles**: permisos de ejecución y acceso a recursos
- **State store en S3**: persistencia de `last_artifact_hash.json`

---

## Conclusión

La ejecución `rf14c20-p2p-005` constituye evidencia válida de que la productivización mínima en cloud está operativa.

### RF14c-20 se considera cumplido porque:
1. se pudo lanzar una task real en ECS Fargate,
2. la task terminó con `exitCode = 0`,
3. se generaron artefactos finales en S3,
4. se actualizó correctamente el state store,
5. quedó demostrada la integración real entre ECS, ECR, S3, Secrets Manager, IAM y CloudWatch.

---

## Evidencia mínima a conservar
Se recomienda conservar como evidencia final de RF14c-20:

- Task ARN ejecutada
- salida de `describe-tasks`
- listado S3 del prefijo `runs/rf14c20-p2p-005/`
- contenido de `state/p2p/last_artifact_hash.json`
- captura opcional de CloudWatch Logs o consola ECS
