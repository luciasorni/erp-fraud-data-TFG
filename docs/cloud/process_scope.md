# RF14c-04 — Estrategia multi-dominio P2P/O2C y parametrización de ejecución

## Objetivo
Permitir que la misma arquitectura cloud ejecute distintos dominios del proyecto sin duplicar infraestructura.

La ejecución del pipeline se controlará mediante una variable de entorno:

```text
PROCESS_SCOPE=p2p|o2c|both
```

## Decisión de diseño
Se utilizará una única infraestructura cloud para todos los dominios:
- una sola imagen Docker,
- un solo repositorio ECR,
- un solo ECS Cluster,
- una sola Task Definition,
- un único esquema general de almacenamiento en S3.

La variación entre ejecuciones se controlará mediante parámetros, no mediante infraestructuras separadas.

## Valores válidos de PROCESS_SCOPE

### 1. `p2p`
Ejecuta exclusivamente el dominio **Purchase to Pay**.

Casos típicos:
- pruebas centradas en compras,
- validación aislada del flujo P2P,
- runs parciales.

### 2. `o2c`
Ejecuta exclusivamente el dominio **Order to Cash**.

Casos típicos:
- pruebas centradas en ventas/cobros,
- validación aislada del flujo O2C,
- runs parciales.

### 3. `both`
Ejecuta ambos dominios en el mismo run lógico.

Casos típicos:
- ejecución completa del sistema,
- comparación y cobertura total del pipeline,
- demostraciones end-to-end.

## Reglas de funcionamiento

### Regla 1
`PROCESS_SCOPE` es obligatorio en modo cloud.

### Regla 2
Solo se aceptan tres valores:
- `p2p`
- `o2c`
- `both`

Cualquier otro valor debe provocar error controlado.

### Regla 3
El mismo `run_id` debe dejar claro qué scope se ha ejecutado en `run_metadata.json`.

### Regla 4
Aunque `PROCESS_SCOPE=both`, la trazabilidad interna debe seguir permitiendo distinguir artefactos y resultados por dominio.

## Impacto técnico esperado

### Runner
El runner debe resolver `PROCESS_SCOPE` al inicio y decidir qué ramas ejecutar.

### Metadata
`run_metadata.json` debe incluir al menos:
- `run_id`
- `process_scope`
- `artifact_hash`
- `timestamp`

### Logs
Los logs deben reflejar claramente el scope del run.

### Outputs
La salida del run debe permitir identificar si corresponde a:
- P2P
- O2C
- BOTH

## Ejemplos

### Ejecución P2P
```text
PROCESS_SCOPE=p2p
```

### Ejecución O2C
```text
PROCESS_SCOPE=o2c
```

### Ejecución completa
```text
PROCESS_SCOPE=both
```

## Decisión adoptada
Se adopta como estrategia oficial:

- `PROCESS_SCOPE=p2p|o2c|both`
- una sola infraestructura cloud
- parametrización por ejecución
- sin separación física de infraestructuras por dominio

## Nota
Esta tarea define la estrategia funcional de ejecución multi-dominio, pero no implementa todavía la lógica en código. Esa implementación se realizará en tareas posteriores del requisito, especialmente en la adaptación del runner cloud.

## Criterio de done de RF14c-04
RF14c-04 se considera terminado cuando:
1. existe `docs/cloud/process_scope.md`,
2. quedan definidos los valores válidos de `PROCESS_SCOPE`,
3. queda decidido que la infraestructura será única,
4. queda decidido que la variación será por parámetro de ejecución,
5. queda claro el comportamiento esperado para `p2p`, `o2c` y `both`.
