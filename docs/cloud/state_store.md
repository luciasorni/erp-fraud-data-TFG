# RF14c-10 — State store en S3

## Objetivo
Implementar un almacenamiento de estado mínimo en S3 para persistir el último `artifact_hash` conocido por ámbito de ejecución (`process_scope`).

## Fichero de estado
El fichero de estado se llamará:

```text
last_artifact_hash.json
```

## Ubicación por `PROCESS_SCOPE`
Partiendo de `S3_STATE_URI`, la clave se construye así:

- `p2p`  -> `.../state/p2p/last_artifact_hash.json`
- `o2c`  -> `.../state/o2c/last_artifact_hash.json`
- `both` -> `.../state/both/last_artifact_hash.json`

## Estructura del estado

```json
{
  "last_artifact_hash": "string",
  "last_run_id": "string",
  "process_scope": "p2p|o2c|both",
  "updated_at": "ISO-8601 UTC"
}
```

## Implementación realizada (RF14c-10)

Archivo:
- `src/erp_fraud/storage/state_store.py`

Funciones:
- `build_state_s3_location(...)`
- `read_last_artifact_hash_state(...)`
- `write_last_artifact_hash_state(...)`

Decisiones:
- lectura tolerante: si no existe el fichero devuelve `None` (no fatal).
- escritura idempotente por overwrite del mismo objeto S3.
- reutiliza `parse_s3_uri` y `create_s3_client` de `src/erp_fraud/storage/s3_io.py`.
- no implementa comparación ni decisión de relanzamiento.

## Fuera de alcance en RF14c-10
- comparación automática `artifact_hash` actual vs previo.
- trigger/relaunch automático.
- integración EventBridge/Lambda/ECS end-to-end.
