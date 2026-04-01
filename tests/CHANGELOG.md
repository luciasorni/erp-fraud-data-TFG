# Test Catalog Changelog

Registro de cambios del catálogo de tests (`tests/catalog`).

## 2026-03-04

### Added

- `TST-DUPLICATE-POSTINGS` `v1.0.0`
  - Alta inicial del test P2P para detección de duplicados por proveedor, documento, posición e importe.
  - `data_requirements` exactos sobre `fraud_1`: `Kreditor`, `Belegnummer`, `Position`, `Betrag`.
  - Lógica SQL referenciada en `sql/tests/tst_duplicate_postings.sql`.

- `TST-UNUSUAL-AMOUNT-BY-VENDOR` `v1.0.0`
  - Alta inicial del test P2P para detección de importes atípicos por proveedor.
  - `data_requirements` exactos sobre `fraud_1`: `Kreditor`, `Betrag`, `Transaktionsart`.
  - Lógica SQL referenciada en `sql/tests/tst_unusual_amount_by_vendor.sql`.

## 2026-04-01

### Added

- `TST-ROUND-DOLLAR-PAYMENTS` `v1.0.0`
  - Nuevo TestSpec ACFE para detección de pagos de importe redondo.
  - `data_requirements` exactos sobre `fraud_1`: `Kreditor`, `Betrag`, `Belegnummer`.
  - Lógica SQL prevista en `sql/tests/tst_round_dollar_payments.sql` (implementación en RF13-03).

- `TST-JUST-BELOW-AUTH-THRESHOLD` `v1.0.0`
  - Detección de importes justo por debajo de umbrales de autorización.
  - `data_requirements` exactos: `Kreditor`, `Belegnummer`, `Betrag`.

- `TST-SPLIT-PAYMENTS-NEAR-LIMIT` `v1.0.0`
  - Detección de facturas fraccionadas para superar umbral agregado.
  - `data_requirements` exactos: `Kreditor`, `Belegnummer`, `Position`, `Betrag`.

- `TST-INVOICE-SEQUENCE-GAPS` `v1.0.0`
  - Detección de saltos atípicos en secuencia de `Belegnummer` por proveedor.
  - `data_requirements` exactos: `Kreditor`, `Belegnummer`.

- `TST-NEGATIVE-QUANTITY-RECEIPTS` `v1.0.0`
  - Detección de líneas con `Menge` negativa.
  - `data_requirements` exactos: `Kreditor`, `Belegnummer`, `Material`, `Menge`.

- `TST-DUPLICATE-MATERIAL-ITEMS` `v1.0.0`
  - Detección de material duplicado en mismo proveedor/documento/posición.
  - `data_requirements` exactos: `Kreditor`, `Belegnummer`, `Position`, `Material`.
