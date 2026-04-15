# GitHub Action — Publish ECR (RF14c-27)

Workflow: `.github/workflows/ecr-publish-main.yml`

## Qué hace

En `push` a `main` (y `workflow_dispatch`):
- checkout,
- asume un rol AWS por OIDC,
- valida identidad AWS y cuenta esperada,
- valida que el repositorio ECR existe,
- login en ECR,
- build Docker,
- push tag por SHA corto,
- push `latest`.

## Parámetros fijados

- Región: `eu-west-1`
- Cuenta: `798350130349`
- ECR repo: `tfg-fraud-dev-ecr-pipeline`

## Requisito de autenticación

- `AWS_ROLE_TO_ASSUME`
  ARN del rol IAM que GitHub Actions debe asumir por OIDC.

El workflow es deliberadamente fail-fast:
- si falta `AWS_ROLE_TO_ASSUME`, falla;
- si la identidad asumida no pertenece a la cuenta `798350130349`, falla;
- si no existe el repo ECR `tfg-fraud-dev-ecr-pipeline`, falla.

No hay fallback a access keys estáticas para evitar ejecuciones ambiguas o verdes falsos.

## Configuración exacta OIDC

1. En AWS IAM, crea o reutiliza un proveedor OIDC para GitHub:
   `https://token.actions.githubusercontent.com`
2. Crea un rol IAM asumible por GitHub Actions con permisos mínimos sobre ECR.
3. Usa una trust policy restringida al repo y rama `main`.
4. Guarda el ARN del rol en el secret del repositorio GitHub:
   `AWS_ROLE_TO_ASSUME`

Trust policy de ejemplo:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::798350130349:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:luciasorni/erp-fraud-data-TFG:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

Permisos mínimos esperables en el rol:
- `ecr:GetAuthorizationToken`
- `ecr:BatchCheckLayerAvailability`
- `ecr:InitiateLayerUpload`
- `ecr:UploadLayerPart`
- `ecr:CompleteLayerUpload`
- `ecr:PutImage`
- `ecr:BatchGetImage`
- `ecr:DescribeRepositories`

## Uso

- Automático: merge/push a `main`.
- Manual: pestaña Actions -> `ECR Publish Main` -> `Run workflow`.

## Resultado esperado

- Imagen publicada en:
  - `798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline:<sha>`
  - `798350130349.dkr.ecr.eu-west-1.amazonaws.com/tfg-fraud-dev-ecr-pipeline:latest`

## Comportamiento ante fallo

- Si OIDC no está configurado correctamente, el workflow falla antes del login/push.
- No se “silencia” el publish ni se marca verde si no ha publicado.
