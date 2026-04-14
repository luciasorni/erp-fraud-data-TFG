# RF14c-18 — ECS Cluster y red mínima

## Objetivo
Crear el cluster ECS y dejar preparada la configuración mínima de red para ejecutar tareas Fargate del pipeline.

## Configuración adoptada
- **Región**: `eu-west-1`
- **Cluster ECS**: `tfg-fraud-dev-ecs-cluster`
- **VPC**: default VPC
- **Subnets**: subnets públicas de la default VPC
- **Security group**: `tfg-fraud-dev-ecs-sg`
- **Inbound**: none
- **Outbound**: allowed
- **Assign public IP**: `ENABLED` en la ejecución de la task

## Justificación
Para la primera versión del TFG se adopta una configuración simple de Fargate:
- cluster ECS estándar,
- subnets públicas,
- public IP asignada a la task,
- SG sin inbound.

Esto permite que la task pueda:
- descargar imagen desde ECR,
- enviar logs a CloudWatch,
- acceder a Secrets Manager,
- acceder a S3 y otros endpoints necesarios.

## Recursos creados

### Cluster
- `tfg-fraud-dev-ecs-cluster`

### Security group
- `tfg-fraud-dev-ecs-sg`

## Verificación
Comandos recomendados:

```bash id="6vbppo"
aws ecs describe-clusters \
  --clusters tfg-fraud-dev-ecs-cluster \
  --region eu-west-1 \
  --profile tfg-fraud-dev

aws ec2 describe-vpcs \
  --filters Name=isDefault,Values=true \
  --region eu-west-1 \
  --profile tfg-fraud-dev

aws ec2 describe-security-groups \
  --filters Name=group-name,Values=tfg-fraud-dev-ecs-sg \
  --region eu-west-1 \
  --profile tfg-fraud-dev
```
**Nota: La asignación efectiva de subnets, security group y assignPublicIp=ENABLED se utilizará en la Task Definition / RunTask posteriores, no se fija completamente en el cluster en sí.

##Criterio de done de RF14c-18

RF14c-18 se considera terminado cuando:
existe el cluster ECS,
está identificada la default VPC,
están identificadas las subnets públicas a usar,
existe el security group sin inbound,
queda documentada la estrategia de red para Fargate.