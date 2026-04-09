# RF11-10 — Data Dictionary O2C mínimo

Fecha: 2026-04-10  
Estado: Cerrado

## 1) Entregables

1. Código generador:
- `src/erp_fraud/storage/o2c_data_dictionary.py`

2. Script de ejecución:
- `scripts/run_rf11_o2c_data_dictionary.py`

3. Artefactos generados:
- `docs/o2c/artifacts/rf11_10_o2c_data_dictionary.json`
- `docs/o2c/artifacts/rf11_10_o2c_data_dictionary.md`

## 2) Criterio de construcción

El diccionario se genera automáticamente desde:

1. `config/canonical_schema_o2c.yaml`
2. `config/column_mapping_o2c.yaml`

Cada entrada incluye al menos:

1. `table`, `column`, `type`, `description`
2. `required` (si el campo es obligatorio)
3. `process_step`
4. `source_candidates`
5. `cast`, `default`

## 3) Ejecución

```bash
python3 scripts/run_rf11_o2c_data_dictionary.py \
  --run-id rf11-10-dd \
  --out-dir run_results \
  --canonical-schema-config config/canonical_schema_o2c.yaml \
  --mapping-config config/column_mapping_o2c.yaml \
  --write-docs-artifacts
```

Salida en run:

- `run_results/<run_id>/rf11_10_o2c_data_dictionary.json`
- `run_results/<run_id>/rf11_10_o2c_data_dictionary.md`

## 4) Validación

Tests:

1. `tests/test_rf11_o2c_data_dictionary.py`
  - generación con entidades mínimas O2C
  - escritura JSON/MD válida

## 5) Nota de alcance

Este diccionario es mínimo y orientado a implementación RF11.  
La ampliación con ejemplos reales y `used_in_tests` O2C se completa al definir la matriz hipótesis->tests->evidencias de RF11-11.
