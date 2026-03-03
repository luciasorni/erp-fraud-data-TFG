# Datos (Fase 1)

## Fuente

- Dataset: `erp_fraud_data.zip`
- Origen funcional: `ERP Fraud Data`
- Alcance operativo actual: `joint_datasets/` (P2P)

## Alcance de uso

- En Fase 1 se usa solo `joint_datasets/` para acelerar prototipo y validación.
- `raw_data/` queda fuera de alcance en esta etapa.

## Tablas cargadas (P2P / joint)

Durante la verificación actual se cargan en DuckDB:

- `column_information`
- `fraud_1`
- `fraud_1_expls`
- `fraud_2`
- `fraud_2_expls`
- `fraud_3`
- `fraud_3_expls`
- `normal_1`
- `normal_2`

## Trazabilidad de datos

Artefactos principales por ejecución (`run_results/<run_id>/`):

- `schema_summary.json`: esquema real cargado (tablas/columnas/tipos)
- `run_metadata.json`: contexto del run (`run_id`, `dataset_hash`, timestamp, versiones)
- `ingest_logs.jsonl`: eventos de ingesta por tabla

Hash reproducible del dataset:

- `dataset_hash` calculado sobre contenido de ficheros en `joint_datasets/`

## Diccionario de datos

- `data_dictionary.json`: formato máquina, generado desde `schema_summary.json`
- `data_dictionary.md`: formato humano para documentar campos y uso

Campos mínimos por entrada:

- `table`, `column`, `type`, `description`, `examples`, `used_in_tests`

## Reglas técnicas de preparación

Antes de cargar a DuckDB:

- limpieza técnica de strings (`trim`, normalización de nulls textuales)
- normalización de tipos:
  - fechas -> `datetime`
  - importes -> numérico
  - IDs -> `string`

## Estado de calidad de documentación

- El diccionario está generado para todas las columnas del esquema actual.
- Los campos críticos para tests iniciales tienen descripción mínima y ejemplos.
- `used_in_tests` se completa desde catálogo cuando los TestSpec estén definidos.
