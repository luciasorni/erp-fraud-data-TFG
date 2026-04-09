# RF11-09 — Mapping explícito `raw_data -> O2C` (casts + defaults)

Fecha: 2026-04-10  
Estado: Cerrado

## 1) Entregable principal

- `config/column_mapping_o2c.yaml`

Define por entidad/campo:

1. `source_candidates` (columnas SAP candidatas),
2. `cast` esperado,
3. `default` controlado.

## 2) Cobertura del mapping

Incluye las 5 entidades canónicas:

1. `o2c_order`
2. `o2c_delivery`
3. `o2c_invoice`
4. `o2c_collection`
5. `o2c_customer`

## 3) Integración en runtime

Archivo:

- `src/erp_fraud/storage/o2c_transform.py`

Comportamiento:

1. carga y valida sintaxis de `column_mapping_o2c.yaml`,
2. exige que existan mapeos para todas las entidades soportadas,
3. aborta con error controlado si el mapping está incompleto,
4. registra `mapping_config_path` en metadata de salida del transform.

## 4) Integración CLI/scripts

1. `src/erp_fraud/cli/main.py`
- nuevo flag: `--o2c-mapping-config`
- default: `config/column_mapping_o2c.yaml`

2. `scripts/run_rf11_o2c_transform.py`
- nuevo flag: `--mapping-config`

## 5) Validación

Tests cubiertos/actualizados:

1. `tests/test_rf11_o2c_transform.py` (payload incluye `mapping_config_path`)
2. `tests/test_rf15e_cli_kb_integration.py` (default de `o2c_mapping_config`)

## 6) Siguiente tarea

`RF11-10` — data dictionary O2C mínimo enlazado a este mapping y al schema canónico.
