# RF14c-08 — Capa S3 IO

## Objetivo
Implementar una capa reutilizable de acceso a S3 para:
- descargar inputs y artefactos al inicio del run,
- subir outputs al final del run.

Esta capa debe ser genérica y no debe asumir todavía toda la lógica del runner cloud.

## Alcance de esta tarea
Incluye:
- parseo de URIs S3,
- descarga de ficheros desde un prefijo S3 a un directorio local,
- subida de un directorio local a un prefijo S3,
- funciones helper reutilizables para inputs, artefactos y outputs.

No incluye:
- cálculo de `artifact_hash`,
- lectura/escritura de `last_artifact_hash.json`,
- resolución completa del runner cloud,
- generación de `run_id`,
- ejecución del pipeline.

## Operaciones mínimas esperadas

### Descarga
La capa debe poder descargar:
- `inputs/datasets/...`
- `inputs/docs/...`
- `artifacts/prompts/...`
- `artifacts/catalogs/...`
- `artifacts/mappings/...`

desde S3 hacia un directorio local de trabajo.

### Subida
La capa debe poder subir:
- outputs locales del run

hacia:

```text
runs/<run_id>/
```

## Implementación (RF14c-08)

Archivo:
- `src/erp_fraud/storage/s3_io.py`

Funciones genéricas:
- `parse_s3_uri(uri, allow_empty_prefix=True)`
- `download_s3_prefix_to_local_dir(...)`
- `upload_local_dir_to_s3_prefix(...)`

Helpers finos:
- `download_required_inputs(...)`
- `upload_run_outputs(...)`

Notas:
- preserva rutas relativas en upload/download.
- crea directorios locales automáticamente.
- tolera prefijo vacío (`s3://bucket`).
- no incluye hash de artefacto, state store ni lógica de runner cloud.
