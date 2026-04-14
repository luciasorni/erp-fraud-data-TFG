# RF14c-01 — Arquitectura AWS mínima (job)

## Objetivo
Ejecutar el pipeline multiagente como un **job reproducible en AWS** con:
- imagen en ECR,
- ejecución en ECS Fargate mediante `run-task`,
- inputs/outputs/state en S3,
- logs en CloudWatch Logs,
- secretos en Secrets Manager,
- permisos mínimos con IAM.

La primera versión prioriza una arquitectura **simple y operativa** para ejecutar el pipeline de forma manual y reproducible. La automatización completa por eventos se deja para tareas posteriores del requisito.

## Alcance de esta fase
Incluye arquitectura mínima de ejecución batch (no servicio web persistente):
- 1 tarea ECS Fargate por `run_id`
- el contenedor ejecuta el pipeline y finaliza
- la salida se persiste en S3 bajo el prefijo `runs/<run_id>/`

No incluye todavía:
- interfaz gráfica (Streamlit)
- API intermedia (FastAPI)
- scheduler programado
- trigger automático por cambio de artefactos
- optimizaciones avanzadas de red
- EFS / persistencia avanzada del índice vectorial

## Decisiones de arquitectura

### 1. Compute — ECS Fargate
El pipeline se ejecutará como una **task puntual** en ECS Fargate usando `run-task`.

Motivo:
- no requiere gestionar servidores,
- encaja con un pipeline pesado y batch,
- permite una ejecución aislada por `run_id`,
- simplifica CPU/memoria/red/IAM por ejecución.

### 2. Imagen — ECR
La imagen Docker del pipeline se almacenará en un repositorio privado de Amazon ECR.

Motivo:
- integración nativa con ECS,
- versionado por tags,
- despliegue reproducible de la misma imagen en local y cloud.

### 3. Storage — S3
S3 será el almacenamiento principal para:
- inputs (`inputs/`)
- artefactos (`artifacts/`)
- estado (`state/`)
- resultados (`runs/<run_id>/`)

Motivo:
- almacenamiento simple y duradero,
- accesible desde ECS,
- válido como punto de entrada futuro para triggers por cambio de ficheros.

### 4. Logs — CloudWatch Logs
Los logs estructurados del contenedor se enviarán a CloudWatch Logs.

Motivo:
- troubleshooting centralizado,
- consulta del output de la task sin entrar al contenedor,
- evidencia de ejecución cloud.

### 5. Secretos — Secrets Manager
Los secretos de ejecución se guardarán en AWS Secrets Manager, por ejemplo:
- `OPENAI_API_KEY`
- `LANGSMITH_API_KEY`

Motivo:
- evita guardar claves en el repositorio o en la imagen,
- ECS permite inyectarlos en la task definition.

### 6. IAM — separación de roles
Se usarán dos roles diferentes:

#### a) Task execution role
Usado por ECS/Fargate para:
- hacer pull de la imagen desde ECR,
- enviar logs a CloudWatch,
- recuperar secretos inyectados en la task.

#### b) Task role
Usado por la aplicación dentro del contenedor para:
- leer de S3,
- escribir en S3,
- acceder a otros servicios AWS que necesite el pipeline.

### 7. Networking mínimo
Para la primera versión se usará:
- **VPC default**
- **subnets públicas**
- **Assign public IP = enabled**
- **security group sin reglas inbound**
- **egress permitido**

Motivo:
- es la opción más simple para que la task pueda:
  - sacar la imagen desde ECR,
  - escribir logs,
  - acceder a Secrets Manager,
  - llamar a servicios externos si el pipeline los necesita.

Nota:
esta configuración se elige por simplicidad operativa para el TFG. En una arquitectura más endurecida se preferirían subnets privadas + NAT o VPC endpoints.

## Flujo mínimo end-to-end
1. Se construye la imagen Docker del pipeline.
2. Se publica la imagen en ECR.
3. Se lanza una task ECS Fargate con `run-task`.
4. El contenedor:
   - descarga inputs y artefactos desde S3,
   - ejecuta el pipeline,
   - genera outputs locales,
   - sube resultados a `s3://.../runs/<run_id>/`.
5. Los logs se almacenan en CloudWatch Logs.
6. Las trazas LLM se registran en LangSmith si están activadas.

## Preparación para tareas posteriores
Esta arquitectura deja preparado el sistema para:
- parametrizar ejecución por dominio (`PROCESS_SCOPE=p2p|o2c|both`)
- añadir scheduler con EventBridge
- añadir trigger automático por cambio de artefactos mediante S3 + Lambda/EventBridge
- añadir interfaz gráfica o API como capa superior, sin cambiar el motor de ejecución

## Criterio de done de RF14c-01
RF14c-01 se considera terminado cuando:
1. esta arquitectura queda documentada,
2. quedan decididos los componentes mínimos,
3. queda decidido el networking mínimo,
4. queda clara la separación entre execution role y task role,
5. el documento sirve de base para ejecutar RF14c-02 en adelante sin ambigüedades.

**Nota de diseño:** la interfaz gráfica (por ejemplo Streamlit) y una posible API intermedia (por ejemplo FastAPI) se tratarán en un requisito separado y no forman parte del núcleo cloud mínimo de RF14c.