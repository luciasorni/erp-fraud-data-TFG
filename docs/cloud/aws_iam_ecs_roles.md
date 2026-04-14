# RF14c-17 — IAM roles para ECS/Fargate

## Objetivo
Crear los roles IAM necesarios para ejecutar el pipeline en ECS/Fargate con separación correcta entre permisos de infraestructura y permisos de aplicación.

## Roles creados

### 1. Execution role
- **Nombre**: `tfg-fraud-dev-ecs-execution-role`
- **Uso**: usado por ECS/Fargate para pull de imagen desde ECR, envío de logs a CloudWatch e inyección de secretos desde Secrets Manager.

#### Policies
- Managed policy:
  - `AmazonECSTaskExecutionRolePolicy`
- Inline policy:
  - acceso de lectura a los secretos:
    - `tfg-fraud-dev-sm-openai-api-key`
    - `tfg-fraud-dev-sm-langsmith-api-key`

### 2. Task role
- **Nombre**: `tfg-fraud-dev-ecs-task-role`
- **Uso**: usado por la aplicación dentro del contenedor para acceder a S3.

#### Policies
- Inline policy:
  - `s3:ListBucket` sobre `tfg-fraud-dev-euw1-lucia01`
  - `s3:GetObject`
  - `s3:PutObject`
  sobre `arn:aws:s3:::tfg-fraud-dev-euw1-lucia01/*`

## Trust relationship
Ambos roles usan `ecs-tasks.amazonaws.com`.

## Verificación
Comandos usados:
```bash
aws iam get-role --role-name tfg-fraud-dev-ecs-execution-role --profile tfg-fraud-dev
aws iam get-role --role-name tfg-fraud-dev-ecs-task-role --profile tfg-fraud-dev
aws iam list-attached-role-policies --role-name tfg-fraud-dev-ecs-execution-role --profile tfg-fraud-dev
aws iam list-role-policies --role-name tfg-fraud-dev-ecs-execution-role --profile tfg-fraud-dev
aws iam list-role-policies --role-name tfg-fraud-dev-ecs-task-role --profile tfg-fraud-dev
```
## Criterio de done de RF14c-17

RF14c-17 se considera terminado porque:
1. existe un execution role para ECS/Fargate,
2. existe un task role para la aplicación,
3. el execution role permite ECR, CloudWatch Logs y lectura de secretos,
4. el task role permite acceso S3 mínimo necesario, ambos roles quedan documentados.