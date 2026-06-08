# Catálogo antifraude

El catálogo real está formado por especificaciones YAML y SQL asociado.

## Rutas

- P2P: `tests/catalog`
- O2C: `tests/catalog_o2c`
- SQL: `sql/tests`
- Schema/loader/runner: `src/erp_fraud/catalog`

## Contrato

El contrato de una prueba se define en:

- `src/erp_fraud/catalog/test_spec_schema.py`

Campos obligatorios principales:

- `id`
- `version`
- `name`
- `fraud_type`
- `red_flag_id`
- `process_step`
- `description`
- `source`
- `expected_output`
- `evidence_columns`
- `data_requirements`
- `logic`

El schema admite `logic.implementation_type=sql|python`. Las 17 pruebas revisadas del catálogo actual usan `sql` y referencian `logic.sql_ref`.

## Resumen de pruebas

| test_id | Proceso | fraud_type | SQL |
|---|---|---|---|
| `TST-DUPLICATE-MATERIAL-ITEMS` | P2P | `duplicate_entry` | `sql/tests/tst_duplicate_material_items.sql` |
| `TST-DUPLICATE-POSTINGS` | P2P | `duplicate_payment` | `sql/tests/tst_duplicate_postings.sql` |
| `TST-INVOICE-SEQUENCE-GAPS` | P2P | `invoice_number_anomaly` | `sql/tests/tst_invoice_sequence_gaps.sql` |
| `TST-JUST-BELOW-AUTH-THRESHOLD` | P2P | `authorization_bypass` | `sql/tests/tst_just_below_auth_threshold.sql` |
| `TST-LARGE-EVEN-DOLLAR-ENTRIES` | P2P | `suspicious_payment_pattern` | `sql/tests/tst_large_even_dollar_entries.sql` |
| `TST-NEGATIVE-QUANTITY-RECEIPTS` | P2P | `inventory_anomaly` | `sql/tests/tst_negative_quantity_receipts.sql` |
| `TST-ROUND-DOLLAR-PAYMENTS` | P2P | `suspicious_payment_pattern` | `sql/tests/tst_round_dollar_payments.sql` |
| `TST-SPLIT-PAYMENTS-NEAR-LIMIT` | P2P | `authorization_bypass` | `sql/tests/tst_split_payments_near_limit.sql` |
| `TST-UNUSUAL-AMOUNT-BY-VENDOR` | P2P | `amount_anomaly` | `sql/tests/tst_unusual_amount_by_vendor.sql` |
| `TST-UNUSUAL-POSTING-TIMES` | P2P | `timing_anomaly` | `sql/tests/tst_unusual_posting_times.sql` |
| `TST-O2C-CLEARING-ANOMALY` | O2C | `collection_manipulation` | `sql/tests/tst_o2c_clearing_anomaly.sql` |
| `TST-O2C-DELIVERY-QUANTITY-MISMATCH` | O2C | `delivery_manipulation` | `sql/tests/tst_o2c_delivery_quantity_mismatch.sql` |
| `TST-O2C-DISCOUNT-POLICY-BREACH` | O2C | `discount_abuse` | `sql/tests/tst_o2c_discount_policy_breach.sql` |
| `TST-O2C-INVOICE-AMOUNT-ANOMALY` | O2C | `invoice_amount_anomaly` | `sql/tests/tst_o2c_invoice_amount_anomaly.sql` |
| `TST-O2C-INVOICE-DATE-SEQUENCE` | O2C | `invoice_sequence_anomaly` | `sql/tests/tst_o2c_invoice_date_sequence.sql` |
| `TST-O2C-NEGATIVE-DELIVERY-QUANTITY` | O2C | `quantity_manipulation` | `sql/tests/tst_o2c_negative_delivery_quantity.sql` |
| `TST-O2C-PRICE-OUTLIER` | O2C | `price_manipulation` | `sql/tests/tst_o2c_price_outlier.sql` |

## Limitaciones

- El catálogo no implica cobertura universal de fraude.
- La ejecución depende de que existan las tablas y columnas requeridas.
- P2P y O2C usan familias de datos distintas.
- Las pruebas actuales están implementadas como SQL controlado; no se genera SQL libre por LLM.
