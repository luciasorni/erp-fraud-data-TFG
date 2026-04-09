# RF11 — Referencia de Proceso y Puntos de Inserción de Fraude (P2P + O2C)

Fecha: 2026-04-09  
Fuentes funcionales:
- capturas aportadas por negocio (P2P/O2C con desviaciones potenciales),
- `docs/external/red_flags_final.pdf`,
- `docs/external/data_analytics_tests.pdf`,
- `docs/external/data_analysis_slides_for_pdf.pdf`.

## 1) Objetivo

Fijar una referencia funcional única para que el diseño técnico RF11 (O2C) y el ajuste de lo ya implementado en P2P sigan los mismos puntos de fraude del proceso real.

## 2) P2P — desviaciones de proceso observadas

Desviaciones mostradas en el flujo P2P:

1. Manipulación de precio/cantidad en ítem de PO.
2. Creación manual de PO.
3. Cambio de PO.
4. Cambio de cantidad recibida (GR).
5. Introducción de scrap.
6. Manipulación de cantidades desde planificación.

## 3) O2C — desviaciones de proceso observadas

Desviaciones mostradas en el flujo O2C:

7. Manipulación de precios de venta.
8. Manipulación de descuentos por cliente.
9. Cambio de pedido de cliente.
10. Manipulación de entrega.

## 4) Traducción a señales analíticas (qué debemos modelar)

1. Precio anómalo vs baseline (producto, cliente, periodo).
2. Descuento fuera de política o patrón histórico.
3. Cambios repetidos/tardíos de pedido tras hitos clave.
4. Entrega modificada en secuencia no esperada (cantidades, fechas, parcialidades).
5. Cantidades negativas o incoherentes entre pedido/entrega/factura.
6. Fraccionamiento para evitar umbrales (aprobación/autorización).

## 5) Impacto en lo ya implementado (P2P actual)

Cobertura parcial ya existente (tests RF13 implementados):

- `TST-UNUSUAL-AMOUNT-BY-VENDOR`
- `TST-JUST-BELOW-AUTH-THRESHOLD`
- `TST-SPLIT-PAYMENTS-NEAR-LIMIT`
- `TST-NEGATIVE-QUANTITY-RECEIPTS`
- `TST-DUPLICATE-POSTINGS`
- `TST-DUPLICATE-MATERIAL-ITEMS`
- `TST-INVOICE-SEQUENCE-GAPS`
- `TST-ROUND-DOLLAR-PAYMENTS`

Lectura técnica:

- Sí cubrimos señales de importe/cantidad/duplicidad en tramo de factura-contable.
- No cubrimos todavía de forma completa las desviaciones tempranas de proceso (creación/cambio de PO y eventos O2C de pricing/discount/order-change/delivery-change).

## 6) Impacto directo en RF11 (O2C)

Este mapa condiciona las tareas RF11-03+ así:

1. `RF11-03` (canonical schema O2C) debe incluir campos para capturar eventos de cambio (pedido/precio/descuento/entrega).
2. `RF11-05` (transform raw->canónico) debe preservar trazabilidad temporal y de actor/objeto para detectar secuencias anómalas.
3. `RF11-11` (matriz hipótesis->tests->evidencia) debe nacer de estos 10 puntos de desviación, no de heurísticas genéricas.
4. `RF11-12` (taxonomía) debe mapear estas desviaciones a ramas de fraude oficiales (fraud tree) y `fraud_type` interno.

## 7) Regla de diseño acordada

Para RF11, una hipótesis o test O2C nuevo no entra si no se puede enlazar a:

1. paso de proceso (`order`, `delivery`, `invoice`, `collection`),
2. desviación de referencia (lista anterior),
3. evidencia de datos concreta (columnas + claves + evento temporal).

## 8) Nota de aplicabilidad de fuentes externas

Los documentos en `docs/external/` siguen siendo válidos para O2C como marco de:

1. red flags de proceso,
2. diseño de pruebas analíticas,
3. priorización de señales de fraude.

En RF11 se usan como referencia metodológica, y el mapping operativo final se formaliza en:

- `docs/o2c/artifacts/rf11_11_o2c_hypothesis_matrix.csv`
- `config/fraud_tree_taxonomy.yaml`.
