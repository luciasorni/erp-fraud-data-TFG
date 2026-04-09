# P2P — Cobertura Actual vs Proceso de Negocio (y Gaps)

Fecha: 2026-04-09

## 1) Resumen corto

Sí cuadra técnicamente, pero el alcance actual de P2P es **parcial**:

1. Cobertura fuerte en `invoice_posting`.
2. Cobertura puntual en `goods_receipt`.
3. Cobertura baja/casi nula en `purchase_order` y `payment_clearing` end-to-end.

Por eso puede parecer que “P2P completo” no encaja con los tests actuales: el pipeline está bien para fase actual, pero no representa todo el proceso de negocio P2P en igual profundidad.

## 2) Qué tests P2P tenemos y en qué paso caen

### `invoice_posting` (8 tests)

1. `TST-DUPLICATE-POSTINGS`
2. `TST-UNUSUAL-AMOUNT-BY-VENDOR`
3. `TST-INVOICE-SEQUENCE-GAPS`
4. `TST-JUST-BELOW-AUTH-THRESHOLD`
5. `TST-SPLIT-PAYMENTS-NEAR-LIMIT`
6. `TST-ROUND-DOLLAR-PAYMENTS`
7. `TST-UNUSUAL-POSTING-TIMES`
8. `TST-LARGE-EVEN-DOLLAR-ENTRIES`

### `goods_receipt` (1 test)

1. `TST-NEGATIVE-QUANTITY-RECEIPTS`

### `invoice_posting` orientado a ítems/material (1 test)

1. `TST-DUPLICATE-MATERIAL-ITEMS`

## 3) Relación con el diagrama P2P de negocio

Del flujo P2P completo (planificación/precio -> PO -> cambios PO -> GR -> invoice -> clear invoice):

1. Cubierto parcialmente:
- señales en GR (`negative quantities`).
- señales de invoice y autorización.

2. No cubierto de forma explícita todavía:
- creación manual de PO,
- cambios de PO (precio/cantidad),
- scrap como evento propio de proceso,
- cierre de invoice/pago en cadena completa con control de evento.

## 4) Conclusión operativa

No hay inconsistencia de implementación; hay **desfase de profundidad** entre:

1. El diagrama de proceso de negocio completo.
2. La cobertura analítica actual (centrada en tramo de factura/asiento).

## 5) Qué hacemos para corregir la lectura (sin romper nada)

1. Mantener P2P actual como baseline estable (no tocar lógica ya validada).
2. Documentar claramente “cobertura actual vs cobertura objetivo”.
3. Extender cobertura por etapas:
- primero O2C (RF11) reutilizando arquitectura,
- luego cierre de gaps P2P tempranos en un mini-paquete posterior (PO/change events), si lo priorizas.

## 6) Mensaje recomendando para defensa/demo

“El sistema ya ejecuta 10 tests P2P reales con evidencia trazable, pero la cobertura está enfocada en invoice/GR. El proceso P2P completo está modelado como referencia de negocio y se amplía por iteraciones para cubrir eventos tempranos (PO/change) y cierre final.”
