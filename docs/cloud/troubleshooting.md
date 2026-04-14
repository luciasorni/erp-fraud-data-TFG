# Troubleshooting Cloud RF14c

## 1) Task ECS termina con `exitCode=1`

### Diagnóstico rápido
1. `describe-tasks` (stop reason / exit code)
2. `get-log-events` del stream más reciente
3. verificar inputs/artifacts en S3

### Comandos
```bash
aws ecs describe-tasks --cluster tfg-fraud-dev-ecs-cluster --tasks <TASK_ARN> --region eu-west-1 --profile tfg-fraud-dev
aws logs describe-log-streams --log-group-name /ecs/tfg-fraud-dev-pipeline --region eu-west-1 --profile tfg-fraud-dev --order-by LastEventTime --descending --max-items 5
aws logs get-log-events --log-group-name /ecs/tfg-fraud-dev-pipeline --log-stream-name '<STREAM>' --region eu-west-1 --profile tfg-fraud-dev --limit 200
```

## 2) `No existe config de pesos: config/weights.yaml`

### Causa típica
- `weights.yaml` no está en `artifacts/mappings/<scope>/` ni en `artifacts/mappings/shared/`.

### Acción
```bash
aws s3 cp config/weights.yaml s3://tfg-fraud-dev-euw1-lucia01/artifacts/mappings/p2p/weights.yaml --profile tfg-fraud-dev --region eu-west-1
aws s3 cp config/weights.yaml s3://tfg-fraud-dev-euw1-lucia01/artifacts/mappings/shared/weights.yaml --profile tfg-fraud-dev --region eu-west-1
```

## 3) `No existe mapping de red flags: config/red_flags_mapping.yaml`

### Causa típica
- `red_flags_mapping.yaml` no está en S3 para el scope o shared.

### Acción
```bash
aws s3 cp config/red_flags_mapping.yaml s3://tfg-fraud-dev-euw1-lucia01/artifacts/mappings/p2p/red_flags_mapping.yaml --profile tfg-fraud-dev --region eu-west-1
aws s3 cp config/red_flags_mapping.yaml s3://tfg-fraud-dev-euw1-lucia01/artifacts/mappings/shared/red_flags_mapping.yaml --profile tfg-fraud-dev --region eu-west-1
```

## 4) Error al hacer push `latest` a ECR (`...pipelineatest`)

### Causa típica
- Typo en nombre de repo/tag al hacer `docker push`.

### Acción
Verificar `ECR_REPO=tfg-fraud-dev-ecr-pipeline` y repetir:
```bash
docker push 798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline:latest
```

## 5) No aparecen runs en `runs/<run_id>/`

### Causa típica
- Falla previa durante ejecución cloud (no llega a `upload_run_outputs`).

### Acción
- revisar logs del task,
- verificar que `inputs/` y `artifacts/` requeridos existen,
- relanzar task con nuevo `run_id`.

## 6) State store no se actualiza

### Comportamiento esperado
- Si el run falla, **no** se actualiza state.
- Solo en éxito se escribe `state/<scope>/last_artifact_hash.json`.

## 7) Trigger RF14c-23 no lanza ECS

### Checks
1. regla EventBridge activa y filtrando prefijos correctos.
2. Lambda recibe evento y compara hash.
3. si hash no cambia, el comportamiento correcto es `skip`.

### Comando útil
```bash
aws s3 cp s3://tfg-fraud-dev-euw1-lucia01/state/<scope>/last_artifact_hash.json - --profile tfg-fraud-dev
```

## 8) Scheduler RF14c-22 no dispara task

### Checks
- schedule habilitado,
- role de scheduler con permisos `ecs:RunTask` + `iam:PassRole`,
- network config válido (subnets/sg).

## 9) LangSmith link no disponible en evidencia final

### Nota
- No inventar link.
- Si no quedó persistido, documentar “insertar manualmente tras ejecución final”.
