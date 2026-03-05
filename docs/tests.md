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
5. `description` (`string`)  
   Qué detecta el test y su intención.
6. `source` (`object`)  
   Metadatos de procedencia del test:
   - `catalog` (`string`) obligatorio
   - `reference` (`string`) obligatorio
   - `url` (`string`) opcional
7. `data_requirements` (`object`)  
   Requisitos de datos para ejecutar el test:
   - `tables` (`array`) obligatorio
   - cada elemento debe incluir:
     - `table` (`string`)
     - `required_columns` (`array[string]`)
     - `required_columns_exact` (`array[string]`) opcional pero recomendado  
       Si se informa, debe contener exactamente los mismos campos que `required_columns`.
8. `logic` (`object`)  
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
