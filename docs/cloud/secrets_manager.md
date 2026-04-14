# RF14c-16 — Secrets Manager

## Objetivo
Crear y registrar los secretos necesarios para la ejecución cloud del pipeline en AWS Secrets Manager, evitando almacenar claves sensibles en el repositorio, en la imagen Docker o en la configuración pública.

## Configuración adoptada
- **Región**: `eu-west-1`
- **Cuenta AWS**: `798350130349`

## Secretos creados

### 1. OpenAI
- **Nombre**: `tfg-fraud-dev-sm-openai-api-key`
- **Descripción**: `OpenAI API key for TFG fraud pipeline`

### 2. LangSmith
- **Nombre**: `tfg-fraud-dev-sm-langsmith-api-key`
- **Descripción**: `LangSmith API key for TFG fraud pipeline`

## Criterio de nombrado
Se adopta la convención:

```text
tfg-fraud-dev-sm-<secret-name>
```

donde:
- `tfg-fraud` = proyecto
- `dev` = entorno
- `sm` = Secrets Manager

## Uso previsto
Estos secretos se inyectarán más adelante en la Task Definition de ECS/Fargate para que el contenedor pueda acceder a:

- `OPENAI_API_KEY`
- `LANGSMITH_API_KEY`

sin necesidad de incluirlos en:
- el repositorio,
- `.env.example`,
- el Dockerfile,
- la imagen publicada en ECR.

## Comandos de verificación ejecutados

### Verificar secreto de OpenAI
```bash
aws secretsmanager describe-secret \
  --secret-id tfg-fraud-dev-sm-openai-api-key \
  --region eu-west-1 \
  --profile tfg-fraud-dev
```

**Salida relevante:**
```json
{
  "ARN": "arn:aws:secretsmanager:eu-west-1:798350130349:secret:tfg-fraud-dev-sm-openai-api-key-9hb3T7",
  "Name": "tfg-fraud-dev-sm-openai-api-key",
  "Description": "OpenAI API key for TFG fraud pipeline",
  "VersionIdsToStages": {
    "f11fc5c4-9d59-42ca-a172-76f45e9c2d4c": [
      "AWSCURRENT"
    ]
  }
}
```

### Verificar secreto de LangSmith
```bash
aws secretsmanager describe-secret \
  --secret-id tfg-fraud-dev-sm-langsmith-api-key \
  --region eu-west-1 \
  --profile tfg-fraud-dev
```

**Salida relevante:**
```json
{
  "ARN": "arn:aws:secretsmanager:eu-west-1:798350130349:secret:tfg-fraud-dev-sm-langsmith-api-key-UAxu6f",
  "Name": "tfg-fraud-dev-sm-langsmith-api-key",
  "Description": "LangSmith API key for TFG fraud pipeline",
  "VersionIdsToStages": {
    "57251f0b-1daa-40da-848f-e58fcd6c7112": [
      "AWSCURRENT"
    ]
  }
}
```

## Estado actual
Ambos secretos existen correctamente en AWS Secrets Manager y tienen una versión activa marcada como `AWSCURRENT`.

## Rotación y mantenimiento
Para esta fase del TFG:
- **no se activa rotación automática**
- la actualización del valor del secreto se hará manualmente si cambia la clave
- el nombre del secreto se mantiene estable para no romper referencias posteriores desde ECS

## Integración posterior con ECS
Más adelante, en la Task Definition de ECS/Fargate, se referenciarán estos secretos mediante sus ARN para poblar variables de entorno del contenedor.

La integración prevista será conceptualmente:

- secreto OpenAI → variable `OPENAI_API_KEY`
- secreto LangSmith → variable `LANGSMITH_API_KEY`

## Buenas prácticas adoptadas
- no exponer claves reales en documentación
- no guardar secretos en `.env.example`
- no incluir secretos en el repositorio
- separar secretos de configuración no sensible

## Criterio de done de RF14c-16
RF14c-16 se considera terminado porque:
1. existen los secretos necesarios en AWS Secrets Manager,
2. ambos secretos son verificables por CLI,
3. tienen versión activa `AWSCURRENT`,
4. quedan documentados sus nombres y uso previsto para ECS.
