# Matriz consolidada de hipótesis, tests y evidencias

## 1. Objetivo

Este documento consolida la gobernanza de la relación:

`hipótesis -> test_id -> evidence_columns -> business keys -> fraud_type`

para las dos familias de proceso soportadas por el proyecto:

- `P2P`
- `O2C`

No sustituye a las matrices específicas por familia; actúa como índice único y criterio común de trazabilidad.

## 2. Artefactos oficiales

### P2P

- Documento: `docs/p2p/rf13_p2p_hypothesis_matrix.md`
- CSV: `docs/p2p/artifacts/rf13_p2p_hypothesis_matrix.csv`
- Validador: `src/erp_fraud/storage/p2p_hypothesis_matrix.py`
- Script: `scripts/run_rf13_p2p_hypothesis_matrix.py`

### O2C

- Documento: `docs/o2c/rf11_11_o2c_hypothesis_matrix.md`
- CSV: `docs/o2c/artifacts/rf11_11_o2c_hypothesis_matrix.csv`
- Validador: `src/erp_fraud/storage/o2c_hypothesis_matrix.py`
- Script: `scripts/run_rf11_o2c_hypothesis_matrix.py`

## 3. Estructura común de la matriz

Ambas matrices mantienen la misma semántica de trazabilidad:

- `hypothesis_id`: identificador único de la hipótesis.
- `description`: descripción breve del patrón sospechoso.
- `fraud_type`: tipología de fraude asociada.
- `process_step`: etapa del proceso donde aplica.
- `test_id`: test antifraude que operacionaliza la hipótesis.
- `evidence_columns`: columnas mínimas de evidencia que justifican el hallazgo.
- `business_key_fields`: claves mínimas para trazabilidad y drilldown.
- `test_status`: `implemented` o `planned`.

## 4. Reglas de validación comunes

La validación automática comprueba, según familia de proceso:

- que el `test_id` existe en el catálogo correspondiente;
- que `fraud_type` coincide con el `TestSpec`;
- que `evidence_columns` son válidas para la entidad o tablas del modelo;
- que `business_key_fields` son compatibles con las keys mínimas de drilldown;
- que la combinación `hypothesis_id + test_id` es única;
- que un test marcado como `implemented` es realmente ejecutable.

## 5. Uso en el sistema

Esta matriz se usa para soportar:

- consistencia entre catálogo de tests y taxonomía de fraude;
- trazabilidad de la explicación (`explanations`, `second_level_analysis`);
- validación de que las columnas mostradas como evidencia son reales;
- coherencia entre findings, drilldown y scoring;
- documentación de cobertura por proceso.

## 6. Cobertura actual

### P2P

La matriz P2P cubre las hipótesis y tests ampliados de `RF13` sobre compras, recepción, facturación y pagos, alineados con las evidencias reales del dataset.

### O2C

La matriz O2C cubre ventas, delivery, invoice y collection, incluyendo:

- delivery mismatch,
- clearing anomaly,
- anomalies de invoice,
- price outlier,
- discount policy breach.

## 7. Evidencia de verificación

Tests relacionados:

- `tests/test_rf13_p2p_hypothesis_matrix.py`
- `tests/test_rf11_o2c_hypothesis_matrix.py`

Artefactos de validación por run:

- `run_results/<run_id>/rf13_p2p_hypothesis_matrix_validation.json`
- `run_results/<run_id>/rf11_11_o2c_hypothesis_matrix_validation.json`

## 8. Conclusión

El proyecto no mantiene una única matriz monolítica para todas las familias, sino dos matrices específicas y validadas automáticamente. Este documento consolida su papel común y actúa como referencia única para backlog, README y memoria.
