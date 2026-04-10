# RF11-11 — Matriz O2C `hipótesis -> tests -> evidencias`

## 1) Objetivo

Definir una base explícita y validable para planner/explainer en O2C:

- hipótesis funcionales de fraude O2C,
- test IDs objetivo asociados,
- entidades y columnas de evidencia en modelo canónico,
- business keys mínimas para trazabilidad.

La matriz se deriva del documento de referencia de proceso/fraude:
`docs/o2c/rf11_process_fraud_reference.md`.

## 2) Artefactos

- `docs/o2c/artifacts/rf11_11_o2c_hypothesis_matrix.csv`
- `scripts/run_rf11_o2c_hypothesis_matrix.py`
- `src/erp_fraud/storage/o2c_hypothesis_matrix.py`

Salida de verificación por run:

- `run_results/<run_id>/rf11_11_o2c_hypothesis_matrix_validation.json`

## 3) Reglas de validación implementadas

La validación verifica:

1. headers obligatorios de CSV,
2. `process_step` en `{sales_order, delivery, invoice, collection}`,
3. `test_id` con prefijo `TST-O2C-`,
4. `source_deviation_id` con prefijo `O2C-`,
5. `evidence_entity` existente en `config/canonical_schema_o2c.yaml`,
6. `evidence_columns` dentro de campos válidos de la entidad,
7. `business_key_fields` dentro de `config/o2c_entity_identity.yaml`,
8. unicidad de `(hypothesis_id, test_id)`,
9. si `test_status=implemented`, `test_id` debe existir en `tests/catalog_o2c`,
10. si `test_status=implemented`, `fraud_type` y `process_step` deben coincidir con el TestSpec del catálogo.

## 4) Ejecución manual

```bash
python3 scripts/run_rf11_o2c_hypothesis_matrix.py \
  --run-id rf11-11-matrix-check
```

Resultado esperado:

- salida `OK RF11-11 hypothesis matrix: ...`
- JSON de validación con `status=OK`, `rows_total == rows_valid`.

## 5) Cobertura de tests

- `tests/test_rf11_o2c_hypothesis_matrix.py`
  - caso OK sobre matriz oficial,
  - error por `evidence_columns` no válidas,
  - error por duplicado `hypothesis_id+test_id`,
  - error por `test_id` implementado que no existe en catálogo O2C,
  - error por mismatch `fraud_type/process_step` frente al catálogo O2C.

## 6) Notas de alcance

`test_status` distingue cobertura:
- `implemented`: test operativo en catálogo O2C y validado en integración.
- `planned`: test identificado en la matriz pero pendiente de implementación.
