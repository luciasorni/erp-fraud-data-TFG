# RF14c-07 — Configuración por variables de entorno

## Objetivo
Definir la configuración mínima por variables de entorno para ejecutar el pipeline en local y en cloud sin hardcodear rutas ni parámetros de despliegue.

## Variables definidas

### `AWS_REGION`
Región AWS en la que se ejecutan los recursos cloud.

Valor adoptado para este proyecto:

```text
eu-west-1
```

### `RUN_MODE`
Modo de ejecución del pipeline.

Valores válidos:
- `local`
- `cloud`

Significado:
- `local`: ejecución en entorno local
- `cloud`: ejecución dentro de la task ECS/Fargate

### `S3_INPUT_URI`
URI base de entrada en S3 para datasets y documentación.

Valor de referencia:

```text
s3://tfg-fraud-dev-euw1-lucia01/inputs/
```

### `S3_OUTPUT_URI`
URI base de salida en S3 para runs.

Valor de referencia:

```text
s3://tfg-fraud-dev-euw1-lucia01/runs/
```

### `S3_STATE_URI`
URI base de estado en S3.

Valor de referencia:

```text
s3://tfg-fraud-dev-euw1-lucia01/state/
```

### `PROCESS_SCOPE`
Ámbito de ejecución funcional.

Valores válidos:
- `p2p`
- `o2c`
- `both`

### `LANGSMITH_TRACING`
Activa o desactiva trazabilidad en LangSmith.

Valores recomendados:
- `true`
- `false`

### `LANGSMITH_PROJECT`
Nombre del proyecto de trazas en LangSmith.

Valor de referencia:

```text
erp-fraud-tfg
```

## Configuración mínima esperada

### Ejemplo para local
```text
AWS_REGION=eu-west-1
RUN_MODE=local
S3_INPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/inputs/
S3_OUTPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/runs/
S3_STATE_URI=s3://tfg-fraud-dev-euw1-lucia01/state/
PROCESS_SCOPE=p2p
LANGSMITH_TRACING=false
LANGSMITH_PROJECT=erp-fraud-tfg
```

### Ejemplo para cloud
```text
AWS_REGION=eu-west-1
RUN_MODE=cloud
S3_INPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/inputs/
S3_OUTPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/runs/
S3_STATE_URI=s3://tfg-fraud-dev-euw1-lucia01/state/
PROCESS_SCOPE=p2p
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=erp-fraud-tfg
```

## Qué debe ir en `.env.example`
En el repositorio debe existir un `.env.example` sin secretos, que sirva como plantilla pública:

```env
AWS_REGION=eu-west-1
RUN_MODE=local
S3_INPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/inputs/
S3_OUTPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/runs/
S3_STATE_URI=s3://tfg-fraud-dev-euw1-lucia01/state/
PROCESS_SCOPE=p2p
LANGSMITH_TRACING=false
LANGSMITH_PROJECT=erp-fraud-tfg
```

## Qué debe ir en `.env` local
 `.env` local puede empezar exactamente igual que `.env.example`.

Ejemplo recomendado para ahora:

```env
AWS_REGION=eu-west-1
RUN_MODE=local
S3_INPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/inputs/
S3_OUTPUT_URI=s3://tfg-fraud-dev-euw1-lucia01/runs/
S3_STATE_URI=s3://tfg-fraud-dev-euw1-lucia01/state/
PROCESS_SCOPE=p2p
LANGSMITH_TRACING=false
LANGSMITH_PROJECT=erp-fraud-tfg
```


## Compatibilidad con el flujo actual (local/real)
Para no romper el stack actual de pruebas reales (`llm_mode=real`), `.env.example` mantiene placeholders no secretos para:
- `OPENAI_API_KEY=__set_me__`
- `LANGSMITH_API_KEY=__set_me__`

En despliegue cloud productivo, estos secretos deben venir de Secrets Manager/Task Definition y no quedar en claro.

## Decisión técnica para la implementación
Según la revisión del proyecto, el punto central correcto para integrar estas variables sin romper la estructura actual es:

- `src/erp_fraud/cli/main.py:651` en `_resolve_run_settings`
- manteniendo coherencia con `src/erp_fraud/config/run_defaults.py`
- sin romper la lectura actual de LangSmith en:
  - `src/erp_fraud/graph/observability.py`
  - `src/erp_fraud/graph/nodes/common.py`

La opción más limpia es crear:
- `src/erp_fraud/config/env.py`

y hacer que `cli/main.py` y los módulos del grafo consuman esa capa común.

## Criterio de done de RF14c-07
RF14c-07 se considera terminado cuando:
1. existe `docs/cloud/env_vars_cloud.md`,
2. existe `.env.example`,
3. queda documentado qué va en `.env` local,
4. quedan definidas las variables mínimas de entorno,
5. queda claro qué archivo del proyecto debe tocarse para integrarlas sin romper la estructura.
