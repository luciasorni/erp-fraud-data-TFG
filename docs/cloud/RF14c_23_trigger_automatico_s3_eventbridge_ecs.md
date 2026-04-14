# RF14c-23 — Trigger automático por cambio de artefactos en S3

> Documento consolidado RF14c: `docs/cloud/cloud_aws.md`  
> Cierre final de aceptación: `docs/cloud/rf14c_final_verification.md`

## Objetivo
Disparar automáticamente una ejecución cloud del pipeline cuando cambien artefactos relevantes almacenados en S3, sin depender de lanzamientos manuales ni exclusivamente de una programación fija.

La primera versión del trigger automático se limita al scope **p2p**, porque ya está validado end-to-end en cloud y permite demostrar el patrón técnico completo con el menor riesgo posible.

---

## Alcance de esta fase
Incluye:

- recepción de eventos de cambio en S3 mediante EventBridge,
- filtrado de eventos por bucket y prefijos concretos,
- lanzamiento automático de una task ECS Fargate,
- ejecución del pipeline en `RUN_MODE=cloud`,
- persistencia de resultados en S3,
- actualización del state store por scope.

No incluye todavía:

- discriminación dinámica del scope a partir del artefacto cambiado,
- enrutado separado por `o2c` o `both`,
- lógica de deduplicación avanzada a nivel EventBridge,
- interfaz gráfica,
- confirmaciones manuales intermedias.

---

## Decisión de diseño
Aunque en el futuro la capa de interfaz pueda necesitar `both`, para **RF14c-23** se valida primero el trigger automático sobre **p2p**.

Motivo:
- `p2p` ya funciona en cloud,
- reduce el número de variables en la validación,
- permite demostrar el patrón evento → ECS → run cloud,
- evita mezclar al mismo tiempo automatización por eventos y orquestación multi-scope.

La extensión a `both` se puede hacer después reutilizando la misma arquitectura.

---

## Arquitectura elegida

### Flujo
1. Un objeto es creado o actualizado en S3.
2. S3 publica el evento en EventBridge.
3. Una regla EventBridge filtra solo los cambios relevantes.
4. La regla lanza una task ECS Fargate sobre el cluster existente.
5. La task ejecuta el pipeline en modo cloud con:
   - `RUN_MODE=cloud`
   - `PROCESS_SCOPE=p2p`
6. El pipeline genera outputs en `runs/<run_id>/`.
7. El state store de `p2p` se actualiza si la ejecución termina correctamente.

---

## Prefijos vigilados
La regla debe escuchar únicamente estos prefijos del bucket principal:

- `artifacts/prompts/`
- `artifacts/catalogs/`
- `artifacts/mappings/`

---

## Prefijos excluidos de la automatización
No se debe disparar el pipeline por cambios en:

- `runs/`
- `state/`

Motivo:
estos prefijos contienen resultados y estado interno del propio pipeline, por lo que escucharlos podría provocar bucles o ejecuciones innecesarias.

---

## Razón para usar EventBridge + Lambda + ECS
Se elige:

- **S3 Event**
- **EventBridge Rule**
- **Lambda trigger**
- **ECS RunTask**

porque la versión final de RF14c-23 requiere comparar `artifact_hash` antes de decidir el lanzamiento de ECS.

Motivo:
- evita relanzamientos innecesarios cuando no hay cambio efectivo de artefactos,
- mantiene la decisión de re-ejecución en una capa explícita y trazable (Lambda),
- reutiliza la infraestructura ECS ya validada para la ejecución real del pipeline,
- conserva separación clara entre detección de cambio (evento), decisión (Lambda) y ejecución (ECS).

---

## Configuración funcional esperada

### Evento origen
- bucket: `tfg-fraud-dev-euw1-lucia01`
- source: `aws.s3`
- detail-type: `Object Created`

### Filtro
Se aceptan únicamente eventos cuyo `detail.object.key` empiece por alguno de estos prefijos:

- `artifacts/prompts/`
- `artifacts/catalogs/`
- `artifacts/mappings/`

### Target de la regla EventBridge
- servicio: AWS Lambda
- función: `tfg-fraud-dev-rf14c23-trigger`

### Configuración esperada en Lambda (resumen)
- `BUCKET_NAME=tfg-fraud-dev-euw1-lucia01`
- `PROCESS_SCOPE=p2p` (en esta fase validada)
- `CLUSTER_ARN=arn:...:cluster/tfg-fraud-dev-ecs-cluster`
- `TASK_DEF_ARN=arn:...:task-definition/tfg-fraud-dev-task:<rev>`
- `SUBNETS=subnet-091fb9bd171d238aa,subnet-00cd0a8035d8f7dd6,subnet-0329d6462aeb6fdf7`
- `SECURITY_GROUPS=sg-0bbcc120180a92672`

### Lo que lanza Lambda cuando detecta cambio real
Lambda invoca `ecs:RunTask` con overrides equivalentes a:

```json
{
  "containerOverrides": [
    {
      "name": "erp-fraud-pipeline",
      "command": ["run", "--input-zip", "erp_fraud_data.zip"],
      "environment": [
        { "name": "RUN_MODE", "value": "cloud" },
        { "name": "PROCESS_SCOPE", "value": "p2p" }
      ]
    }
  ]
}
```

---

## Evidencia esperada para dar RF14c-23 por válido
RF14c-23 se considerará terminado cuando se demuestre que:

1. existe una regla EventBridge asociada a eventos S3,
2. la regla filtra solo los prefijos de artefactos definidos,
3. un cambio real en S3 dispara la Lambda de RF14c-23,
4. Lambda compara `artifact_hash` actual vs último estado del scope,
5. solo si hay cambio efectivo Lambda lanza una task ECS Fargate,
6. la task arranca con `RUN_MODE=cloud` y `PROCESS_SCOPE=p2p`,
7. el run se refleja en S3 con un nuevo prefijo `runs/<run_id>/`,
8. el state store de `p2p` se actualiza correctamente.

---

## Estrategia de validación recomendada
Para validar el trigger se recomienda:

1. subir un archivo de prueba a:
   - `artifacts/mappings/p2p/`
   o
   - `artifacts/prompts/shared/`
2. esperar el evento automático,
3. comprobar invocación de Lambda y decisión `skip/launch`,
4. si `launch`, comprobar la nueva task en ECS,
5. revisar logs en CloudWatch (Lambda + ECS),
6. comprobar el nuevo run en S3,
7. comprobar `state/p2p/last_artifact_hash.json`.

---

## Resultado esperado de esta fase
La salida final de RF14c-23 debe demostrar que la arquitectura cloud del proyecto soporta no solo:

- ejecución manual,
- ejecución programada,

sino también:

- **re-ejecución automática basada en eventos de cambio de artefactos**.
