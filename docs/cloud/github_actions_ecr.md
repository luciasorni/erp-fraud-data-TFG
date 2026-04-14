# GitHub Action — Publish ECR (RF14c-27)

Workflow: `.github/workflows/ecr-publish-main.yml`

## Qué hace

En `push` a `main` (y `workflow_dispatch`):
- checkout,
- credenciales AWS desde secrets,
- login en ECR,
- build Docker,
- push tag por SHA corto,
- push opcional `latest`.

## Parámetros fijados

- Región: `eu-west-1`
- Cuenta: `798350130349`
- ECR repo: `tfg-fraud-dev-ecr-pipeline`

## Secrets necesarios en GitHub

Recomendado (OIDC):
- `AWS_ROLE_TO_ASSUME` (ARN del rol IAM asumible por GitHub Actions)

Alternativa (credenciales estáticas):
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`

## Uso

- Automático: merge/push a `main`.
- Manual: pestaña Actions -> `ECR Publish Main` -> `Run workflow`.

## Resultado esperado

- Imagen publicada en:
  - `798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline:<sha>`
  - `798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline:latest` (si no se desactiva)

## Limitación

- El workflow no puede verificarse en local sin secrets reales del repositorio GitHub.
