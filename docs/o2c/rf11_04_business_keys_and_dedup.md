# RF11-04 — Business Keys y Deduplicación/Normalización O2C

Fecha: 2026-04-10  
Estado: Cerrado

## 1) Entregable principal

- `config/o2c_entity_identity.yaml`

Define por entidad O2C:

1. clave de negocio (`business_key`),
2. reglas de normalización por campo,
3. estrategia de resolución de duplicados (`duplicate_resolution`),
4. validaciones de integridad entre entidades.

## 2) Claves de negocio definidas

1. `o2c_order`
- `(sales_order_id, sales_order_item_id)`

2. `o2c_delivery`
- `(delivery_id, delivery_item_id)`

3. `o2c_invoice`
- `(company_code, accounting_document_id, fiscal_year)`

4. `o2c_collection`
- `(company_code, receivable_document_id, fiscal_year)`

5. `o2c_customer`
- `customer_id`

## 3) Normalización acordada

Reglas globales:

1. `trim`, `uppercase`, `empty -> null`.
2. Zero-padding SAP (ancho 10 por defecto) para IDs documentales/clientes.
3. Escalas estándar:
- importes `decimal(...,2)`,
- cantidades `decimal(...,3)`.
4. Fechas inválidas: `null + warning` (sin abortar por defecto en esta fase).

## 4) Estrategia de deduplicación

Para todas las entidades:

1. Scope de duplicado = `business_key`.
2. Se conserva fila con mejor `quality_score`.
3. Si empate:
- `latest_ingestion_ts`,
- y después `lexical_row_hash`.

Calidad ponderada por presencia de campos críticos y prioridad de fuente (ej. `LIPS` sobre `LIKP` en delivery; `BSEG` sobre `BKPF` en invoice/collection).

## 5) Integridad cruzada mínima

1. `o2c_delivery -> o2c_order`: warning si claves de referencia no enlazan.
2. `o2c_collection -> o2c_invoice`: warning si no enlaza con clave contable.

## 6) Decisiones y límites

1. Esta definición es declarativa y no rompe P2P.
2. La implementación runtime real de estas reglas queda para:
- `RF11-05` (transform),
- `RF11-06` (validación técnica).
3. Se mantiene compatibilidad hacia atrás: no se modifica pipeline actual de ejecución P2P.

## 7) Criterio de aceptación RF11-04

Cumplido:

1. Business keys explícitas por entidad O2C.
2. Reglas de normalización y deduplicación por entidad.
3. Reglas mínimas de integridad entre entidades para validación posterior.

## 8) Siguiente tarea

`RF11-05` — Implementar transformaciones `raw -> canónico O2C` en DuckDB usando esta definición.
