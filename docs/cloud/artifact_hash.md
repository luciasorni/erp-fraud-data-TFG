# RF14c-09 — Cálculo de artifact_hash

## Objetivo
Calcular un `artifact_hash` reproducible que represente el conjunto de artefactos de entrada que afectan al comportamiento del pipeline y guardarlo en `run_metadata.json`.

## Qué representa `artifact_hash`
`artifact_hash` debe cambiar cuando cambian artefactos relevantes de entrada, por ejemplo:
- prompts,
- catálogos,
- mappings,
- documentación de KB.

No debe cambiar por outputs generados durante el run, logs, timestamps u otros artefactos derivados de ejecución.

## Artefactos incluidos
Según `PROCESS_SCOPE`, el hash debe calcularse sobre los artefactos realmente utilizados en el run.

### Para `PROCESS_SCOPE=p2p`
- prompts compartidos
- prompts de p2p
- catálogos de p2p
- mappings de p2p
- docs compartidos
- docs de p2p

### Para `PROCESS_SCOPE=o2c`
- prompts compartidos
- prompts de o2c
- catálogos de o2c
- mappings de o2c
- docs compartidos
- docs de o2c

### Para `PROCESS_SCOPE=both`
- prompts compartidos
- prompts de p2p
- prompts de o2c
- catálogos de p2p
- catálogos de o2c
- mappings de p2p
- mappings de o2c
- docs compartidos
- docs de p2p
- docs de o2c

## Artefactos excluidos
No deben entrar en el hash:
- `runs/`
- `state/`
- outputs del run
- logs
- `run_metadata.json`
- ficheros temporales
- timestamps de ejecución

## Estrategia de cálculo
La estrategia adoptada será:

1. reunir la lista de ficheros relevantes,
2. ordenar de forma estable por ruta relativa,
3. calcular hash de contenido por fichero,
4. construir un manifiesto estable con rutas y hashes,
5. calcular el hash final del manifiesto serializado.

## Requisitos de implementación
- usar hash de contenido, no `mtime`
- no depender de rutas absolutas del sistema local
- mantener orden determinista
- diferenciar correctamente por `PROCESS_SCOPE`
- integrar el resultado en `run_metadata.json`

## Persistencia mínima esperada
`run_metadata.json` deberá incluir al menos:
- `artifact_hash`
- `process_scope`

Opcionalmente puede incluir también un resumen de artefactos usados para trazabilidad.

## Criterio de done de RF14c-09
RF14c-09 se considera terminado cuando:
1. existe una capa reutilizable para calcular `artifact_hash`,
2. el cálculo depende del `PROCESS_SCOPE`,
3. el hash se basa en contenido y orden estable,
4. el resultado se guarda en `run_metadata.json`,
5. hay tests básicos que demuestran reproducibilidad.

## Implementación realizada
- Capa reusable: `src/erp_fraud/storage/artifact_hash.py`
  - `collect_artifact_files(...)`
  - `compute_file_sha256(...)`
  - `build_artifact_manifest(...)`
  - `compute_artifact_hash(...)`
- Integración mínima en pipeline:
  - `src/erp_fraud/cli/main.py`
  - `src/erp_fraud/storage/run_metadata.py`
- Persistencia en `run_metadata.json`:
  - `artifact_hash`
  - `process_scope`
  - `artifact_files_count` (resumen opcional de trazabilidad)
- Tests:
  - `tests/test_rf14c09_artifact_hash.py`
  - `tests/test_rf14c09_run_metadata.py`
