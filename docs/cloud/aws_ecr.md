# RF14c-14 — Amazon ECR

## Objetivo
Publicar la imagen Docker del pipeline en un repositorio privado de Amazon ECR para su uso posterior desde ECS Fargate.

## Configuración adoptada
- **Cuenta AWS**: `798350130349`
- **Región**: `eu-west-1`
- **Repositorio ECR**: `tfg-fraud-dev-ecr-pipeline`
- **URI del repositorio**: `798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline`

## Resultado de la tarea
La tarea se ha completado correctamente:
- el repositorio ECR existe,
- Docker autentica correctamente contra ECR,
- la imagen se ha construido en local,
- la imagen se ha etiquetado con `git_sha` y `latest`,
- ambas etiquetas se han publicado correctamente en ECR.

## Comandos ejecutados

### 1. Obtener Account ID
```bash
aws sts get-caller-identity --profile tfg-fraud-dev --query Account --output text
```

**Salida:**
```text
798350130349
```

### 2. Crear el repositorio ECR
```bash
aws ecr create-repository \
  --repository-name tfg-fraud-dev-ecr-pipeline \
  --region eu-west-1 \
  --profile tfg-fraud-dev
```

**Resultado relevante:**
- `repositoryName`: `tfg-fraud-dev-ecr-pipeline`
- `repositoryUri`: `798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline`

### 3. Verificar el repositorio
```bash
aws ecr describe-repositories \
  --repository-names tfg-fraud-dev-ecr-pipeline \
  --region eu-west-1 \
  --profile tfg-fraud-dev
```

**Resultado:** repositorio existente y visible en la región correcta.

### 4. Login de Docker contra ECR
```bash
aws ecr get-login-password --region eu-west-1 --profile tfg-fraud-dev | \
docker login --username AWS --password-stdin 798350130349.dkr.ecr.eu-west-1.amazonaws.com
```

**Salida:**
```text
Login Succeeded
```

### 5. Build local de la imagen
```bash
docker build -t erp-fraud-pipeline:rf14c14 .
```

**Resultado:** build completado correctamente.

### 6. Obtener `git_sha`
```bash
git rev-parse --short HEAD
```

**Salida:**
```text
19378a1
```

### 7. Etiquetar la imagen para ECR
```bash
docker tag erp-fraud-pipeline:rf14c14 798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline:19378a1
docker tag erp-fraud-pipeline:rf14c14 798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline:latest
```

### 8. Publicar imagen en ECR
```bash
docker push 798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline:19378a1
docker push 798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline:latest
```

**Resultado relevante:**
- tag `19378a1` publicada correctamente
- tag `latest` publicada correctamente
- digest publicado: `sha256:a6894e01fe7971ec3e5f64e83d49902dcfe7715508122735d8c66afe1de52e1f`

### 9. Verificar imágenes publicadas
```bash
aws ecr list-images \
  --repository-name tfg-fraud-dev-ecr-pipeline \
  --region eu-west-1 \
  --profile tfg-fraud-dev
```

**Resultado relevante:**
- imagen con tag `19378a1`
- imagen con tag `latest`

## Script de automatización
Existe el script:

```text
scripts/build_and_push_ecr.sh
```

Y se le han dado permisos de ejecución:

```bash
chmod +x scripts/build_and_push_ecr.sh
```

## Notas de revisión

### 1. Salida de `docker run --help`
La salida que mostraste de ayuda del CLI del proyecto es correcta y confirma que la imagen arranca y que el entrypoint del contenedor está bien resuelto.

### 2. Imagen base usada
En el build aparece:

```text
python:3.9-slim
```

Esto no es necesariamente un problema.  
Es válido **si coincide con la versión Python soportada por el proyecto**. Conviene mantenerlo así si todo el proyecto y sus dependencias ya funcionan correctamente con Python 3.9.

### 3. Imágenes sin tag en `list-images`
Aparecen también algunos `imageDigest` sin `imageTag`. Esto es normal y no invalida la tarea; lo importante para RF14c-14 es que existen y son utilizables las tags:
- `19378a1`
- `latest`

## Criterio de done de RF14c-14
RF14c-14 se considera terminado porque:
1. existe el repositorio ECR,
2. Docker autentica correctamente contra ECR,
3. la imagen se publica con tag por `git_sha`,
4. la imagen se publica también con tag `latest`,
5. existe script de build/push,
6. queda documentado el proceso.

## Siguiente paso
El siguiente requisito natural es **RF14c-15**, donde se creará el CloudWatch Log Group del job y se dejará preparado el formato de logs estructurados para la task.
