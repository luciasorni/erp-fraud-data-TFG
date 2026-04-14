# RF14c-03 — Preparación de credenciales locales AWS CLI

## Objetivo
Dejar preparada la máquina local para poder interactuar con AWS desde terminal y validar que la cuenta está correctamente accesible desde la CLI.

## Resultado alcanzado
En esta tarea se ha dejado configurado un perfil local de AWS CLI para el proyecto, usando una región fija y un formato de salida homogéneo. Además, se ha validado la identidad efectiva contra AWS mediante STS.

## Decisiones tomadas
- **Herramienta local**: AWS CLI v2
- **Profile utilizado**: `tfg-fraud-dev`
- **Región por defecto**: `eu-west-1`
- **Formato de salida por defecto**: `json`

## Configuración realizada
Se ha configurado AWS CLI mediante un perfil dedicado al proyecto:

```bash
aws configure --profile tfg-fraud-dev
```

La configuración asociada al perfil queda conceptualmente así:

### `~/.aws/config`
```ini
[profile tfg-fraud-dev]
region = eu-west-1
output = json
```

### `~/.aws/credentials`
```ini
[tfg-fraud-dev]
aws_access_key_id = <ACCESS_KEY_ID>
aws_secret_access_key = <SECRET_ACCESS_KEY>
```

## Validación realizada
Se ha validado que AWS CLI puede autenticarse correctamente con la cuenta mediante:

```bash
aws sts get-caller-identity --profile tfg-fraud-dev
```

Este comando confirma:
- que las credenciales son válidas,
- que el perfil está bien configurado,
- y que la CLI está apuntando a una identidad AWS real.

Además, se ha comprobado el identificador de cuenta con:

```bash
aws sts get-caller-identity --profile tfg-fraud-dev --query Account --output text
```

## Identidad registrada
- **Account ID**: `798350130349`

## Uso recomendado en sesiones de trabajo
Para evitar escribir `--profile tfg-fraud-dev` en cada comando, se puede exportar temporalmente el perfil en la terminal:

```bash
export AWS_PROFILE=tfg-fraud-dev
```

Con eso, los siguientes comandos AWS usarán automáticamente ese perfil durante la sesión actual.

## Alcance de la tarea
Esta tarea deja resuelta únicamente la **preparación de credenciales locales y la validación de acceso**.

No incluye todavía:
- creación de buckets S3,
- creación de ECR,
- creación de roles IAM,
- despliegue de ECS,
- ni ejecución del pipeline en cloud.

## Criterio de done
RF14c-03 se considera completada cuando:
1. AWS CLI está instalada y accesible desde terminal.
2. Existe el perfil `tfg-fraud-dev`.
3. La región por defecto es `eu-west-1`.
4. El formato por defecto es `json`.
5. `aws sts get-caller-identity --profile tfg-fraud-dev` devuelve una identidad válida.

## Evidencia mínima asociada
La evidencia mínima de esta tarea consiste en:
- salida de `aws --version`,
- salida de `aws sts get-caller-identity --profile tfg-fraud-dev`,
- y registro del `Account ID` utilizado por el proyecto.
