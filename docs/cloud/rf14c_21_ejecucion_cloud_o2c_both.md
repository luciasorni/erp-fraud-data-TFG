# RF14c-21 — Evidencia de ejecución cloud exitosa para O2C y BOTH

> Documento consolidado RF14c: `docs/cloud/cloud_aws.md`  
> Cierre final de aceptación: `docs/cloud/rf14c_final_verification.md`

## Objetivo
Validar que la productivización cloud no solo funciona para `p2p`, sino también para:

- `PROCESS_SCOPE = o2c`
- `PROCESS_SCOPE = both`

demostrando que el runner cloud soporta múltiples dominios/procesos sobre la misma infraestructura AWS.

---

## Contexto general

### Infraestructura usada
- **Región**: `eu-west-1`
- **Cluster ECS**: `tfg-fraud-dev-ecs-cluster`
- **Bucket S3**: `tfg-fraud-dev-euw1-lucia01`
- **Security Group**: `sg-0bbcc120180a92672`

### Subnets usadas
- `subnet-091fb9bd171d238aa`
- `subnet-00cd0a8035d8f7dd6`
- `subnet-0329d6462aeb6fdf7`

### Launch type
- `FARGATE`

---

# 1. Ejecución cloud para O2C

## Run ID
- `rf14c21-o2c-001`

## Task ARN
```text
arn:aws:ecs:eu-west-1:798350130349:task/tfg-fraud-dev-ecs-cluster/28a43872e29b47989c727f4c5b682e83
```

## Resultado ECS

### Salida de verificación
```json
{
  "lastStatus": "STOPPED",
  "stopCode": "EssentialContainerExited",
  "stoppedReason": "Essential container in task exited",
  "exitCode": 0,
  "containerReason": null
}
```

### Interpretación
La task O2C terminó correctamente y el contenedor salió con `exitCode = 0`, por lo que la ejecución cloud para `PROCESS_SCOPE=o2c` fue satisfactoria.

---

## Evidencia de artefactos generados en S3 (O2C)

### Prefijo
```text
runs/rf14c21-o2c-001/
```

### Salida obtenida
```text
2026-04-14 18:24:46          3 runs/rf14c21-o2c-001/data_dictionary.json
2026-04-14 18:24:46         48 runs/rf14c21-o2c-001/data_dictionary.md
2026-04-14 18:24:46       1706 runs/rf14c21-o2c-001/data_validation_report.json
2026-04-14 18:24:46       2776 runs/rf14c21-o2c-001/ingest_logs.jsonl
2026-04-14 18:24:46         53 runs/rf14c21-o2c-001/ranking.json
2026-04-14 18:24:46        598 runs/rf14c21-o2c-001/ranking.parquet
2026-04-14 18:24:46       3635 runs/rf14c21-o2c-001/report.html
2026-04-14 18:24:46      23559 runs/rf14c21-o2c-001/report.json
2026-04-14 18:24:46       2568 runs/rf14c21-o2c-001/report.md
2026-04-14 18:24:46        463 runs/rf14c21-o2c-001/run_metadata.json
2026-04-14 18:24:46       1229 runs/rf14c21-o2c-001/run_structure.json
2026-04-14 18:24:46      76259 runs/rf14c21-o2c-001/schema_summary.json
2026-04-14 18:24:46        104 runs/rf14c21-o2c-001/test_runs.json
```

### Interpretación
El run O2C generó correctamente los artefactos estándar del pipeline cloud y los persistió en S3.

---

## Evidencia de state store (O2C)

### Salida obtenida
```json
{"last_artifact_hash":"722a9f8d1572b0bd4dd0072373bf8eafb3839cec255b2b974078995ff7810113","last_run_id":"rf14c21-o2c-001","process_scope":"o2c","updated_at":"2026-04-14T16:24:45+00:00"}
```

### Interpretación
El state store de `o2c` se actualizó correctamente tras la ejecución exitosa, registrando hash, run y scope.

---

# 2. Ejecución cloud para BOTH

## Run ID
- `rf14c21-both-001`

## Task ARN
```text
arn:aws:ecs:eu-west-1:798350130349:task/tfg-fraud-dev-ecs-cluster/888d18f6218841a88f62a4e4fbaa7bc8
```

## Resultado ECS

### Salida de verificación
```json
{
  "lastStatus": "STOPPED",
  "stopCode": "EssentialContainerExited",
  "stoppedReason": "Essential container in task exited",
  "exitCode": 0,
  "containerReason": null
}
```

### Interpretación
La task BOTH terminó correctamente y el contenedor salió con `exitCode = 0`, validando el soporte cloud para `PROCESS_SCOPE=both`.

---

## Evidencia de artefactos generados en S3 (BOTH)

### Prefijo
```text
runs/rf14c21-both-001/
```

### Salida obtenida
```text
2026-04-14 18:27:53          3 runs/rf14c21-both-001/data_dictionary.json
2026-04-14 18:27:53         48 runs/rf14c21-both-001/data_dictionary.md
2026-04-14 18:27:53       1706 runs/rf14c21-both-001/data_validation_report.json
2026-04-14 18:27:53       2788 runs/rf14c21-both-001/ingest_logs.jsonl
2026-04-14 18:27:53         53 runs/rf14c21-both-001/ranking.json
2026-04-14 18:27:53        598 runs/rf14c21-both-001/ranking.parquet
2026-04-14 18:27:53       3648 runs/rf14c21-both-001/report.html
2026-04-14 18:27:53      23571 runs/rf14c21-both-001/report.json
2026-04-14 18:27:53       2585 runs/rf14c21-both-001/report.md
2026-04-14 18:27:53        465 runs/rf14c21-both-001/run_metadata.json
2026-04-14 18:27:53       1247 runs/rf14c21-both-001/run_structure.json
2026-04-14 18:27:53      76259 runs/rf14c21-both-001/schema_summary.json
2026-04-14 18:27:53        105 runs/rf14c21-both-001/test_runs.json
```

### Interpretación
El run `both` generó correctamente los artefactos estándar y los persistió en S3, igual que en `p2p` y `o2c`.

---

## Evidencia de state store (BOTH)

### Salida obtenida
```json
{"last_artifact_hash":"e7f967b39060c4bf6b8ed25b7a158ad727aaf3a4b593c05e080447db564d1758","last_run_id":"rf14c21-both-001","process_scope":"both","updated_at":"2026-04-14T16:27:52+00:00"}
```

### Interpretación
El state store de `both` se actualizó correctamente con hash, run y scope.

---

# 3. Preparación previa de artefactos O2C

Antes de la ejecución, se cargaron correctamente en S3 los recursos mínimos necesarios para O2C:

## Dataset O2C
- `inputs/datasets/o2c/erp_fraud_data.zip`

## Documentación O2C
- `inputs/docs/o2c/`

## Catálogo O2C
- `artifacts/catalogs/o2c/*.yaml`

## Mappings O2C
- `artifacts/mappings/o2c/column_mapping_o2c.yaml`
- `artifacts/mappings/o2c/canonical_schema_o2c.yaml`
- `artifacts/mappings/o2c/o2c_entity_identity.yaml`

## Recursos compartidos
- `artifacts/prompts/shared/*.md`
- `artifacts/mappings/shared/red_flags_mapping.yaml`
- `artifacts/mappings/shared/weights.yaml`

### Nota
No existe `artifacts/prompts/o2c/` como fuente local real, pero la ejecución fue exitosa usando los prompts compartidos y los mappings/catálogos específicos.

---

# 4. Conclusión

Las ejecuciones `rf14c21-o2c-001` y `rf14c21-both-001` constituyen evidencia válida de que la infraestructura cloud soporta múltiples scopes de ejecución.

## RF14c-21 se considera cumplido porque:
1. se pudo ejecutar con éxito `PROCESS_SCOPE=o2c`,
2. se pudo ejecutar con éxito `PROCESS_SCOPE=both`,
3. ambas tasks terminaron con `exitCode = 0`,
4. ambas persistieron artefactos estándar en S3,
5. ambos scopes actualizaron correctamente su state store.

---

# 5. Resultado global de RF14c

Con las evidencias ya obtenidas, queda validado en cloud:

- `p2p`
- `o2c`
- `both`

Esto demuestra que la productivización mínima en AWS funciona para los distintos modos de ejecución del proyecto.

---

## Evidencia mínima a conservar
Se recomienda conservar como prueba final:

### Para O2C
- Task ARN
- salida de `describe-tasks`
- listado de `runs/rf14c21-o2c-001/`
- contenido de `state/o2c/last_artifact_hash.json`

### Para BOTH
- Task ARN
- salida de `describe-tasks`
- listado de `runs/rf14c21-both-001/`
- contenido de `state/both/last_artifact_hash.json`
