# RF14c-19 — ECS Task Definition Fargate

## Objetivo
Crear la Task Definition de ECS/Fargate para ejecutar el pipeline en AWS usando la imagen publicada en ECR.

## Configuración adoptada

### Family
- `tfg-fraud-dev-task`

### Launch type
- Fargate

### Network mode
- `awsvpc`

### Execution role
- `tfg-fraud-dev-ecs-execution-role`

### Task role
- `tfg-fraud-dev-ecs-task-role`

### Imagen ECR
- `798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline:19378a1`

### CPU y memoria
- CPU: `2048`
- Memory: `4096`

### Logs
- Log group: `/ecs/tfg-fraud-dev-pipeline`
- Region: `eu-west-1`
- Stream prefix: `ecs`

## Variables fijas en la task definition
- `AWS_REGION=eu-west-1`
- `S3_INPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/inputs/`
- `S3_OUTPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/runs/`
- `S3_STATE_URI=s3://tfg-fraud-dev-euw1-lucia01/state/`
- `LANGSMITH_PROJECT=erp-fraud-tfg`

## Secretos
- `OPENAI_API_KEY` desde `tfg-fraud-dev-sm-openai-api-key`
- `LANGSMITH_API_KEY` desde `tfg-fraud-dev-sm-langsmith-api-key`

## Variables que se pasarán por override en cada run
- `RUN_MODE=cloud`
- `PROCESS_SCOPE=p2p|o2c|both`
- opcionalmente `RUN_ID`

## Criterio de done de RF14c-19
RF14c-19 se considera terminado cuando:
1. existe una Task Definition Fargate registrada,
2. usa la imagen ECR correcta,
3. tiene execution role y task role correctos,
4. tiene logs configurados hacia CloudWatch,
5. tiene env vars y secretos configurados,
6. queda clara la separación entre configuración fija y overrides por run.