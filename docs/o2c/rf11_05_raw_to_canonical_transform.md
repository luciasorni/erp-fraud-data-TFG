# RF11-05 — Transformaciones `raw -> canónico O2C` en DuckDB

Fecha: 2026-04-10  
Estado: Cerrado (implementación base)

## 1) Implementación

Archivos:

1. `src/erp_fraud/storage/o2c_transform.py`
2. `scripts/run_rf11_o2c_transform.py`

## 2) Qué hace

1. Lee configuración:
- `config/canonical_schema_o2c.yaml`
- `config/o2c_entity_identity.yaml`

2. Construye tablas canónicas en DuckDB (`schema o2c`):
- `o2c.o2c_order`
- `o2c.o2c_delivery`
- `o2c.o2c_invoice`
- `o2c.o2c_collection`
- `o2c.o2c_customer`

3. Aplica política de degradación:
- entidades `fail_fast` -> error si faltan tablas obligatorias,
- entidades `soft_fail` -> `SKIPPED` y continúa.

4. Deduplicación inicial por clave de negocio:
- `ROW_NUMBER() OVER (PARTITION BY business_key ORDER BY quality_score DESC, ...)`
- conserva solo `_rn = 1`.

## 3) Ejecución manual

```bash
python3 scripts/run_rf11_o2c_transform.py \
  --db-path erp.duckdb \
  --mapping-config config/column_mapping_o2c.yaml \
  --run-id rf11-05-demo \
  --out-dir run_results
```

Salida de evidencia:

- `run_results/<run_id>/rf11_05_o2c_transform_evidence.json`

## 4) Cobertura de tests

Archivo:

- `tests/test_rf11_o2c_transform.py`

Casos cubiertos:

1. Construcción completa de 5 entidades cuando existen tablas fuente.
2. `soft-fail` de invoice/collection cuando faltan `BKPF/BSEG`.
3. `fail-fast` cuando falta tabla obligatoria de entidad crítica (`VBAK` para `o2c_order`).

## 5) Limitaciones actuales (esperadas en esta fase)

1. El comando `erp-fraud run` aún carga `joint_datasets`; esta transformación asume tablas SAP raw ya presentes en DuckDB.
2. La integración completa del selector de proceso (`process_family`) queda para RF11-07/RF11-08.
3. Mapeo detallado columna a columna quedará afinado en RF11-09.
