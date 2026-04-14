# RF14c-13 — Containerización del pipeline

## Objetivo
Empaquetar el pipeline en una imagen Docker reproducible para poder ejecutarlo en local y, posteriormente, en ECS Fargate.

## Alcance de esta tarea
Incluye:
- creación de `Dockerfile`,
- creación de `.dockerignore`,
- definición del comando/entrypoint del contenedor,
- build local,
- smoke test local.

No incluye:
- publicación en ECR,
- ejecución en ECS,
- Task Definition,
- integración con EventBridge,
- integración con Lambda.

## Requisitos de diseño
- reutilizar el runner actual del proyecto,
- no crear un flujo paralelo distinto solo para Docker,
- mantener compatibilidad con el proyecto actual,
- permitir `RUN_MODE=local` y preparar el camino para `RUN_MODE=cloud`,
- usar una imagen base ligera,
- evitar copiar basura innecesaria al contexto Docker.

## Requisitos técnicos
- incluir dependencias Python necesarias,
- copiar el código fuente y archivos requeridos por el proyecto,
- definir un `WORKDIR` claro,
- dejar un comando de arranque explícito,
- soportar variables de entorno ya introducidas en RF14c-07.

## `.dockerignore`
Debe excluir como mínimo:
- `.git`
- `.venv`
- `__pycache__`
- `.pytest_cache`
- `run_results`
- archivos temporales
- artefactos innecesarios para build

## Smoke test esperado
La imagen debe:
1. construirse correctamente,
2. arrancar sin errores de import básicos,
3. permitir ejecutar el runner del proyecto en local dentro del contenedor.

## Criterio de done de RF14c-13
RF14c-13 se considera terminado cuando:
1. existe `Dockerfile`,
2. existe `.dockerignore`,
3. la imagen builda en local,
4. el contenedor arranca correctamente,
5. el proyecto puede ejecutarse dentro del contenedor en un smoke test local.

## Implementación realizada (RF14c-13)

### Archivos
- `Dockerfile`
- `.dockerignore`

### Comando de arranque del contenedor
La imagen usa el runner real del proyecto:

- `ENTRYPOINT`: `python -m src.erp_fraud.cli.main`
- `CMD` por defecto: `run --input-zip erp_fraud_data.zip`

Esto permite mantener flujo único:
- local: `RUN_MODE=local`
- cloud: `RUN_MODE=cloud`

### Build local
```bash
docker build -t erp-fraud-pipeline:rf14c13 .
```

### Smoke test local (import/CLI)
```bash
docker run --rm erp-fraud-pipeline:rf14c13 --help
```

### Smoke test local (run mínimo)
```bash
docker run --rm \
  -e RUN_MODE=local \
  -e PROCESS_SCOPE=p2p \
  erp-fraud-pipeline:rf14c13 \
  run --input-zip erp_fraud_data.zip --run-id docker-smoke-local
```

### Smoke test local (cloud runner sin AWS real)
Para validar solo que entra por la rama cloud (sin integrar AWS real), usar variables de entorno y comandos de prueba en entorno controlado.
