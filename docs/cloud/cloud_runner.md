# RF14c-11 — Runner cloud no interactivo

## Objetivo
Adaptar el runner del proyecto para soportar un modo de ejecución cloud no interactivo, manteniendo compatibilidad con el modo local existente.

## Requisito de diseño
La ejecución debe depender de `RUN_MODE`:

- `RUN_MODE=local`
- `RUN_MODE=cloud`

El modo local debe seguir funcionando sin cambios de comportamiento no deseados.

## Flujo esperado para `RUN_MODE=cloud`

1. cargar configuración y variables de entorno
2. validar `PROCESS_SCOPE`
3. resolver o generar `run_id`
4. crear un workspace temporal local
5. descargar inputs y artefactos desde S3 al workspace
6. calcular `artifact_hash`
7. leer el estado previo (`last_artifact_hash.json`) desde S3
8. ejecutar el pipeline en local sobre el workspace descargado
9. generar outputs locales
10. actualizar `run_metadata.json` con:
   - `run_id`
   - `process_scope`
   - `artifact_hash`
11. subir outputs a `runs/<run_id>/` en S3
12. actualizar el state store si el run fue exitoso
13. devolver exit code correcto

## Integraciones esperadas
Este runner debe reutilizar:
- la configuración/env de RF14c-07
- la capa S3 IO de RF14c-08
- la lógica de `artifact_hash` de RF14c-09
- la lógica de state store de RF14c-10

## Reglas de comportamiento

### Compatibilidad
No debe romper el flujo local ya existente.

### `run_id`
Debe existir para todo run cloud.
Si no viene dado, debe generarse automáticamente.

### State store
Solo debe actualizarse en caso de ejecución exitosa.

### Outputs
Los outputs cloud deben subirse a:

```text
runs/<run_id>/
```

## Implementación realizada (RF14c-11)

Archivo integrado:
- `src/erp_fraud/cli/main.py`

Punto central del runner:
- `run` (handler `_run_pipeline`) ahora enruta por `RUN_MODE`.
  - `RUN_MODE=local` -> `_run_pipeline_local(...)`
  - `RUN_MODE=cloud` -> `_run_pipeline_cloud(...)`

Flujo cloud implementado:
1. carga settings/env ya resueltos
2. valida `PROCESS_SCOPE`
3. resuelve `run_id`
4. crea workspace temporal
5. descarga inputs desde S3 (`download_required_inputs`)
6. calcula `artifact_hash` (`compute_artifact_hash`)
7. lee estado previo (`read_last_artifact_hash_state`)
8. ejecuta pipeline local en workspace reutilizando el runner actual
9. sube outputs de `run_results/<run_id>/` a `runs/<run_id>/`
10. actualiza state store solo en éxito

No incluido aún:
- ECS/TaskDefinition/EventBridge/Lambda
- comparación hash para abortar ejecución
- relanzamiento automático
