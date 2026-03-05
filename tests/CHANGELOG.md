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

