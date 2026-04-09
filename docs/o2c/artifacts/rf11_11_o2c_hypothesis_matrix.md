# RF11-11 O2C Hypothesis Matrix (Resumen)

Fuente canónica:
`docs/o2c/artifacts/rf11_11_o2c_hypothesis_matrix.csv`

- total hipótesis: 8
- process steps cubiertos: `sales_order`, `delivery`, `invoice`, `collection`
- source deviations usadas: `O2C-07`, `O2C-08`, `O2C-09`, `O2C-10`

## Hipótesis incluidas

1. `HYP-O2C-001` -> `TST-O2C-PRICE-OUTLIER`
2. `HYP-O2C-002` -> `TST-O2C-DISCOUNT-POLICY-BREACH`
3. `HYP-O2C-003` -> `TST-O2C-LATE-ORDER-CHANGES`
4. `HYP-O2C-004` -> `TST-O2C-DELIVERY-QUANTITY-MISMATCH`
5. `HYP-O2C-005` -> `TST-O2C-NEGATIVE-DELIVERY-QUANTITY`
6. `HYP-O2C-006` -> `TST-O2C-INVOICE-AMOUNT-ANOMALY`
7. `HYP-O2C-007` -> `TST-O2C-INVOICE-DATE-SEQUENCE`
8. `HYP-O2C-008` -> `TST-O2C-CLEARING-ANOMALY`
