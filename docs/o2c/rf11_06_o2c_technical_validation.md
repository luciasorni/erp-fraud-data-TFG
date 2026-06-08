# RF11-06 — Validaciones técnicas O2C (canónico)

Fecha: 2026-04-10  
Estado: Cerrado (implementación base)

> Nota de estado: este documento corresponde a la subfase RF11-06. La integración posterior de O2C en el comando `run`, grafo y pruebas de integración está documentada en `docs/o2c/rf11_08_orchestration_process_family.md`, `docs/o2c/rf11_13_o2c_integration_tests.md` y `docs/o2c/rf11_16_final_verification.md`.

## 1) Implementación

Archivos:

1. `src/erp_fraud/storage/o2c_validation.py`
2. `scripts/run_rf11_o2c_validation.py`

## 2) Qué valida

Sobre tablas `o2c.*`:

1. Existencia de tabla por entidad según política `fail_fast` / `soft_fail`.
2. Presencia de campos `required` por entidad.
3. `null_percentage` de campos requeridos.
4. Parseabilidad de requeridos por tipo:
- `date*` -> `TRY_CAST(... AS DATE|TIMESTAMP)`
- `decimal*` -> `TRY_CAST(... AS DOUBLE)`
5. Integridad relacional mínima según `relations` del schema canónico:
- porcentaje de filas no enlazadas en relaciones `from -> to`.

## 3) Salida

Reporte JSON con:

1. `summary.overall_status` (`OK|ERROR`)
2. `critical_errors_count`
3. `warning_findings_count`
4. lista de `checks` con granularidad por entidad y relación.

## 4) Ejecución manual

```bash
python3 scripts/run_rf11_o2c_validation.py \
  --db-path erp.duckdb \
  --run-id rf11-06-demo \
  --out-dir run_results
```

Artefacto:

- `run_results/<run_id>/rf11_06_o2c_validation_report.json`

## 5) Tests

Archivo:

- `tests/test_rf11_o2c_validation.py`

Casos cubiertos:

1. Validación `OK` cuando existen todas las entidades canónicas.
2. Validación `OK` con entidades `soft_fail` ausentes (invoice/collection).
3. Validación `ERROR` cuando faltan entidades `fail_fast` (order/delivery).

## 6) Límites de fase

1. En esta subfase, la validación O2C se implementó inicialmente de forma independiente del comando `erp-fraud run`.
2. La integración posterior en la orquestación general se cerró en RF11-07/RF11-08 y se valida en la documentación final RF11.
