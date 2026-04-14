# RF14c-02 — Región AWS, naming y tags estándar

## Objetivo de la tarea
Dejar cerradas estas decisiones antes de crear recursos en AWS:

1. **Región AWS**
2. **Prefijo y naming estándar**
3. **Convención de tags**
4. **Nombre base del bucket S3**

Esto evita inconsistencias al crear recursos y hace que el despliegue cloud sea más fácil de mantener y documentar.

---

## Decisiones adoptadas

### 1. Región elegida
Se utilizará la región:

```text
eu-west-1
```

**Motivo:**
- es una región europea,
- es una elección estándar y práctica para un TFG,
- simplifica la configuración inicial,
- evita dispersar recursos entre varias regiones.

---

### 2. Convención general de nombres
Formato general:

```text
<project>-<environment>-<resource>-<qualifier>
```

Valores fijados:
- `project = tfg-fraud`
- `environment = dev`

Esto da lugar a un prefijo base común:

```text
tfg-fraud-dev
```

**Ejemplos:**
- `tfg-fraud-dev-ecr-pipeline`
- `tfg-fraud-dev-ecs-cluster`
- `tfg-fraud-dev-task`
- `tfg-fraud-dev-cw-logs`
- `tfg-fraud-dev-sm-openai-api-key`

**Reglas de consistencia:**
- usar siempre minúsculas,
- usar guiones `-` como separador,
- no mezclar nombres distintos para el mismo tipo de recurso,
- mantener la misma región para todos los recursos de RF14c salvo justificación explícita.

---

### 3. Convención especial para buckets S3
Los buckets S3 tienen reglas específicas:
- solo minúsculas,
- usar letras, números y guiones,
- evitar guiones bajos,
- el nombre debe ser **globalmente único**.

Formato elegido:

```text
tfg-fraud-dev-euw1-lucia01
```

Este será el bucket principal del proyecto para RF14c.

**Motivo de esta elección:**
- mantiene el prefijo del proyecto,
- incorpora la región (`euw1`),
- añade un sufijo identificativo (`lucia01`) para aumentar la unicidad.

---

### 4. Convención para prefijos/rutas internas en S3
Dentro del bucket se usará una estructura lógica basada en prefijos. En esta tarea solo se deja decidido el esquema general:

```text
inputs/
artifacts/
state/
runs/
```

La estructura detallada de carpetas se cerrará en **RF14c-05**.

---

## Nombres decididos por tipo de recurso

### ECR
```text
tfg-fraud-dev-ecr-pipeline
```

### ECS Cluster
```text
tfg-fraud-dev-ecs-cluster
```

### ECS Task Definition family
```text
tfg-fraud-dev-task
```

### CloudWatch Log Group
```text
/ecs/tfg-fraud-dev-pipeline
```

### Secrets Manager
```text
tfg-fraud-dev-sm-openai-api-key
tfg-fraud-dev-sm-langsmith-api-key
```

### IAM Roles
```text
tfg-fraud-dev-ecs-execution-role
tfg-fraud-dev-ecs-task-role
```

### Security Group
```text
tfg-fraud-dev-ecs-sg
```

### Bucket S3
```text
tfg-fraud-dev-euw1-lucia01
```

---

## Convención de tags
Se usarán los siguientes tags base en todos los recursos que lo permitan:

```text
tfg-fraud:project = tfg-fraud
tfg-fraud:environment = dev
tfg-fraud:owner = lucia
tfg-fraud:component = <component>
tfg-fraud:managed-by = manual
```

**Ejemplos de `component`:**
- `s3`
- `ecr`
- `ecs`
- `logs`
- `secrets`
- `iam`

**Criterios para los tags:**
- todos en minúsculas,
- sin datos sensibles,
- consistentes en todos los recursos,
- útiles para filtrar, documentar y mantener el despliegue.

---

## Resumen ejecutivo de la decisión
Para RF14c se fija una estrategia simple y consistente:

- **Región:** `eu-west-1`
- **Proyecto:** `tfg-fraud`
- **Entorno:** `dev`
- **Bucket principal:** `tfg-fraud-dev-euw1-lucia01`
- **Prefijo común de recursos:** `tfg-fraud-dev-*`
- **Tags estándar:** definidos y reutilizables en todos los recursos

Esto deja preparado el camino para las tareas siguientes:
- RF14c-03: preparar AWS CLI,
- RF14c-06: crear bucket S3,
- RF14c-14: crear ECR,
- RF14c-15 a RF14c-19: crear logs, secretos, IAM, cluster y task definition.

---

## Criterio de done de RF14c-02
RF14c-02 se considera terminado cuando:

1. la región queda decidida,
2. existe `docs/cloud/aws_naming.md`,
3. queda fijado un prefijo estándar de proyecto,
4. quedan definidos los nombres base de recursos,
5. quedan definidos los tags estándar,
6. queda decidido el nombre del bucket S3.

---

## Valores finales aprobados para este proyecto

```text
REGION = eu-west-1
PROJECT = tfg-fraud
ENVIRONMENT = dev
BUCKET = tfg-fraud-dev-euw1-lucia01
```
