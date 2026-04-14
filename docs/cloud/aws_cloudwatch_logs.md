# RF14c-15 — CloudWatch Log Group

## Objetivo
Crear el grupo de logs de CloudWatch que utilizará posteriormente la task de ECS/Fargate para centralizar los logs del contenedor del pipeline.

## Configuración adoptada
- **Región**: `eu-west-1`
- **Log Group**: `/ecs/tfg-fraud-dev-pipeline`
- **Retención**: `30 days`

## Tags aplicados
- `tfg-fraud:project = tfg-fraud`
- `tfg-fraud:environment = dev`
- `tfg-fraud:owner = lucia`
- `tfg-fraud:component = logs`
- `tfg-fraud:managed-by = manual`

## Comandos ejecutados

### Crear el log group
```bash
aws logs create-log-group   --log-group-name /ecs/tfg-fraud-dev-pipeline   --region eu-west-1   --profile tfg-fraud-dev
```

### Añadir tags
```bash
aws logs tag-resource   --resource-arn arn:aws:logs:eu-west-1:798350130349:log-group:/ecs/tfg-fraud-dev-pipeline   --tags '{
    "tfg-fraud:project":"tfg-fraud",
    "tfg-fraud:environment":"dev",
    "tfg-fraud:owner":"lucia",
    "tfg-fraud:component":"logs",
    "tfg-fraud:managed-by":"manual"
  }'   --region eu-west-1   --profile tfg-fraud-dev
```

### Fijar política de retención
```bash
aws logs put-retention-policy   --log-group-name /ecs/tfg-fraud-dev-pipeline   --retention-in-days 30   --region eu-west-1   --profile tfg-fraud-dev
```

### Verificación
```bash
aws logs describe-log-groups   --log-group-name-prefix /ecs/tfg-fraud-dev-pipeline   --region eu-west-1   --profile tfg-fraud-dev
```

## Resultado de la verificación
La salida de validación confirma:

- `logGroupName`: `/ecs/tfg-fraud-dev-pipeline`
- `retentionInDays`: `30`
- `logGroupClass`: `STANDARD`
- `storedBytes`: `0`

## Uso posterior en ECS
Este log group se utilizará más adelante en la Task Definition de ECS/Fargate mediante `logConfiguration`, con valores de referencia como:

- `logDriver = awslogs`
- `awslogs-group = /ecs/tfg-fraud-dev-pipeline`
- `awslogs-region = eu-west-1`
- `awslogs-stream-prefix = ecs`

## Evidencia de ejecución
Se verificó tanto por consola AWS como por CLI que el grupo de registros existe correctamente y que la retención se ha aplicado.

La salida obtenida fue:

```json
{
  "logGroups": [
    {
      "logGroupName": "/ecs/tfg-fraud-dev-pipeline",
      "creationTime": 1776171722670,
      "retentionInDays": 30,
      "metricFilterCount": 0,
      "arn": "arn:aws:logs:eu-west-1:798350130349:log-group:/ecs/tfg-fraud-dev-pipeline:*",
      "storedBytes": 0,
      "logGroupClass": "STANDARD",
      "logGroupArn": "arn:aws:logs:eu-west-1:798350130349:log-group:/ecs/tfg-fraud-dev-pipeline",
      "deletionProtectionEnabled": false,
      "bearerTokenAuthenticationEnabled": false
    }
  ]
}
```

## Criterio de done de RF14c-15
RF14c-15 se considera terminado porque:
1. existe el log group `/ecs/tfg-fraud-dev-pipeline`,
2. está creado en `eu-west-1`,
3. tiene retención de `30 days`,
4. queda listo para integrarse en la Task Definition de ECS.
