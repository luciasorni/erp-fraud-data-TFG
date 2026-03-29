# RF03 - Esquema TestSpec (v1)

Este documento define el contrato mínimo de un `TestSpec` para el catálogo versionado de tests de fraude.

Referencia funcional de tests antifraude (catálogo base):
- ACFE Anti-Fraud Data Analytics Tests (COSO):  
  `https://www.acfe.com/fraud-resources/fraud-risk-tools---coso/anti-fraud-data-analytics-tests`

## Campos obligatorios

Todos los `TestSpec` deben incluir estos campos:

1. `id` (`string`)  
   Identificador único del test. Formato recomendado: `TST-<NOMBRE>`.
2. `version` (`string`)  
   Versión semántica (`MAJOR.MINOR.PATCH`), por ejemplo `1.0.0`.
3. `name` (`string`)  
   Nombre corto legible.
4. `fraud_type` (`string`)  
   Tipo de fraude o riesgo principal (por ejemplo: `duplicate_payment`).
5. `process_step` (`string`)  
   Paso del proceso P2P al que aplica el control (por ejemplo: `invoice_posting`).
6. `description` (`string`)  
   Qué detecta el test y su intención.
7. `source` (`object`)  
   Metadatos de procedencia del test:
   - `catalog` (`string`) obligatorio
   - `reference` (`string`) obligatorio
   - `url` (`string`) opcional
8. `data_requirements` (`object`)  
   Requisitos de datos para ejecutar el test:
   - `tables` (`array`) obligatorio
   - cada elemento debe incluir:
     - `table` (`string`)
     - `required_columns` (`array[string]`)
     - `required_columns_exact` (`array[string]`) opcional pero recomendado  
       Si se informa, debe contener exactamente los mismos campos que `required_columns`.
9. `expected_output` (`object`)  
   Contrato esperado de salida del test:
   - `primary_entity` (`string`) obligatorio
   - `finding_fields` (`array[string]`) obligatorio
   - `notes` (`string`) opcional
10. `evidence_columns` (`array[string]`)  
   Columnas de evidencia mínimas que debe exponer el hallazgo.
11. `logic` (`object`)  
   Descripción técnica de implementación:
   - `implementation_type` (`string`) obligatorio (`sql` o `python`)
   - `description` (`string`) opcional
   - `sql_ref` (`string`) opcional
   - `python_ref` (`string`) opcional

## Campos opcionales

- `enabled` (`boolean`): activar/desactivar el test en catálogo
- `owner` (`string`): responsable
- `tags` (`array[string]`): etiquetas de clasificación

## Ejemplo (YAML)

```yaml
id: TST-DUPLICATE-INVOICE
version: 1.0.0
name: Duplicate invoice amount+vendor+date
fraud_type: duplicate_payment
process_step: invoice_posting
description: Detecta potenciales pagos duplicados por proveedor, importe y fecha.
source:
  catalog: acfe_coso
  reference: duplicate_payments
  url: https://www.acfe.com/fraud-resources/fraud-risk-tools---coso/anti-fraud-data-analytics-tests
data_requirements:
  tables:
    - table: fraud_1
      required_columns:
        - Vendor_Number
        - Amount_Applied
        - Posting_Date
      required_columns_exact:
        - Vendor_Number
        - Amount_Applied
        - Posting_Date
expected_output:
  primary_entity: invoice_line
  finding_fields:
    - vendor_number
    - amount_applied
    - posting_date
  notes: Salida a nivel de línea de factura.
evidence_columns:
  - Vendor_Number
  - Amount_Applied
  - Posting_Date
logic:
  implementation_type: sql
  description: Agrupar por vendor+amount+posting_date y filtrar count > 1.
  sql_ref: sql/tests/tst_duplicate_invoice.sql
enabled: true
owner: data-risk
tags:
  - p2p
  - duplicate
```

## Implementación de referencia

El esquema de código vive en:
- `src/erp_fraud/catalog/test_spec_schema.py`

## Selección inicial RF03-04 (P2P)

Tests elegidos del catálogo ACFE/COSO para implementación inicial:

1. `TST-DUPLICATE-POSTINGS` (`tests/catalog/tst_duplicate_postings.yaml`)
2. `TST-UNUSUAL-AMOUNT-BY-VENDOR` (`tests/catalog/tst_unusual_amount_by_vendor.yaml`)

Motivo de selección:

- Ambos son controles típicos de P2P (duplicados e importes anómalos).
- Se pueden implementar directamente con SQL sobre una sola tabla (`fraud_1`), sin joins complejos.
- Requieren columnas que ya existen en el dataset actual:
  - Duplicados: `Kreditor`, `Belegnummer`, `Position`, `Betrag`
  - Importes anómalos: `Kreditor`, `Betrag`, `Transaktionsart`

Resultado de verificabilidad actual:

- Los `data_requirements` de ambos TestSpec están cubiertos por el diccionario (`data_dictionary.json`).
- Por tanto, son candidatos válidos para implementar lógica en RF03-05 y RF03-06.

## RF03-07 - Requisitos exactos para validación técnica

Para soportar validación previa a ejecución (RF02b), cada test define las columnas exactas
que bloquean la ejecución si faltan:

- `TST-DUPLICATE-POSTINGS`:
  - `fraud_1.Kreditor`
  - `fraud_1.Belegnummer`
  - `fraud_1.Position`
  - `fraud_1.Betrag`
- `TST-UNUSUAL-AMOUNT-BY-VENDOR`:
  - `fraud_1.Kreditor`
  - `fraud_1.Betrag`
  - `fraud_1.Transaktionsart`

La extracción en código prioriza `required_columns_exact` y cae a `required_columns`
si la lista exacta no está informada.

## RF05-03 - Convención de `entity_key`

Se define una convención única para identificar entidades/hallazgos de forma estable.

Formato:

- `entity_key = key1=value1|key2=value2|...`
- Orden de claves: lexicográfico por nombre de clave
- Separadores reservados:
  - pares: `|`
  - asignación: `=`

Reglas:

- `keys` debe ser un objeto no vacío
- ni nombres ni valores pueden estar vacíos
- ni nombres ni valores pueden contener `|` o `=`

Ejemplos P2P:

- `belegnummer=49000123|kreditor=100045`
- `belegnummer=49000123|kreditor=100045|position=10`

Implementación:

- `src/erp_fraud/catalog/entity_key.py`
  - `build_entity_key(keys)`
  - `parse_entity_key(entity_key)`

## RF05 - ResultSchema y outputs por test

Contrato de salida por test:

- `src/erp_fraud/catalog/result_schema.py`
- campos obligatorios del envelope:
  - `result_schema_version`, `generated_at_utc`
  - `test_id`, `test_version`, `fraud_type`, `status`
  - `finding_count`, `duration_ms`
  - `columns`, `rows`, `metadata`

Validación tabular de hallazgos:

- `src/erp_fraud/catalog/result_schema_validator.py`
- columnas mínimas de hallazgo:
  - `entity_key`
  - `keys`
  - `evidence_columns`
  - `metrics`

Serialización por test:

- `src/erp_fraud/catalog/result_writer.py`
- por `run_id`:
  - `tests_outputs/<test_id>/findings.jsonl`
  - `tests_outputs/<test_id>/findings.parquet` (opcional)
  - `tests_outputs/<test_id>/sample_top20.json`

## RF06-01 - Keys mínimas para drilldown

Definición actual de keys mínimas por test (para reconstruir filas origen):

- `TST-DUPLICATE-POSTINGS`:
  - `kreditor`
  - `belegnummer`
  - `position`
  - `betrag`
- `TST-UNUSUAL-AMOUNT-BY-VENDOR`:
  - `kreditor`
  - `betrag`

Implementación:

- `src/erp_fraud/catalog/drilldown_keys.py`
  - `get_minimum_keys_for_test_id(test_id)`
  - `validate_minimum_keys_for_test_id(test_id, keys)`

## RF06-02 - Hallazgos con `keys` y plantilla segura

Cada hallazgo debe incluir:

- `keys` (json): identificadores mínimos para reconstrucción
- `entity_key`: representación estable de `keys`
- `drilldown_template`:
  - `query_id` de allowlist
  - `params` (solo valores; sin SQL libre)

Implementación:

- `src/erp_fraud/catalog/drilldown_templates.py`
- integración actual en:
  - `src/erp_fraud/catalog/test_execution.py`

## RF06-04 - Límite de salida, filtros y orden en drilldown

La función `drilldown(...)` aplica controles para evitar salidas masivas y mantener consultas seguras:

- `limit_rows`:
  - por defecto `200`
  - máximo permitido `200`
- `order_direction`:
  - solo `ASC` o `DESC`
- `extra_filters`:
  - allowlist por test (actualmente `Transaktionsart`)
  - cualquier filtro fuera de allowlist produce error controlado

Implementación:

- `src/erp_fraud/catalog/drilldown.py`
