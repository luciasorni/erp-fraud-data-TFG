# RF11-12 — Taxonomía O2C alineada con Fraud Tree oficial

## 1) Objetivo

Asegurar que los `fraud_type` usados por O2C en RF11-11:

- están mapeados a ramas oficiales del Fraud Tree,
- usan un mapping único y versionado en config,
- se pueden validar automáticamente (sin revisión manual).

## 2) Fuente oficial y config

- Documento oficial: `docs/external/fraud_type.pdf`
- Config usada por runtime: `config/fraud_tree_taxonomy.yaml`

En RF11-12 se añadieron los `fraud_type` O2C al bloque:
`internal_fraud_type_to_branch`.

## 3) Implementación

- Validador de alineación:
  - `src/erp_fraud/storage/o2c_taxonomy.py`
- Script de ejecución manual:
  - `scripts/run_rf11_o2c_taxonomy.py`

Validaciones aplicadas:

1. cada `fraud_type` presente en la matriz O2C tiene mapping,
2. cada branch destino existe en `branches`,
3. salida consolidada con estado y errores.

## 4) Ejecución manual

```bash
python3 scripts/run_rf11_o2c_taxonomy.py \
  --run-id rf11-12-taxonomy-check
```

Salida:

- `run_results/<run_id>/rf11_12_o2c_taxonomy_validation.json`

## 5) Cobertura de tests

- `tests/test_rf11_o2c_taxonomy.py`
  - `OK` con config actual,
  - `ERROR` cuando faltan mappings en taxonomy.

## 6) Resultado esperado para cierre RF11-12

`status=OK` en validación RF11-12 y cobertura verde de tests RF11 (matriz + taxonomía).
