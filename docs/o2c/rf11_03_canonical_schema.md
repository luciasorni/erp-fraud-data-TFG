# RF11-03 — Modelo Canónico O2C (entidades, claves, relaciones, campos)

Fecha: 2026-04-09  
Estado: Cerrado

## 1) Entregable principal

- `config/canonical_schema_o2c.yaml`

Este archivo define:

1. entidades canónicas O2C,
2. grano de cada entidad,
3. campos `required` y `optional` con tipos y `source_candidates`,
4. claves preliminares,
5. relaciones entre entidades,
6. política de degradación por disponibilidad de tablas.

## 2) Entidades incluidas

1. `o2c_order`
- Grano: línea de pedido de venta.
- Base: `VBAK` + `VBAP` (obligatorias), apoyo `VBPA/KNA1/KONV`.

2. `o2c_delivery`
- Grano: línea de entrega.
- Base: `LIPS` (obligatoria), `LIKP` opcional.

3. `o2c_invoice`
- Grano: línea de documento contable.
- Base proxy: `BKPF` + `BSEG` (por falta de `VBRK/VBRP` en inventario actual).

4. `o2c_collection`
- Grano: evento de clearing/cobro inferido.
- Base: `BSEG` (obligatoria), `BKPF` opcional.

5. `o2c_customer`
- Grano: maestro de cliente.
- Base: `KNA1` obligatoria, `KNB1` opcional.

## 3) Relaciones canónicas modeladas

1. `o2c_order -> o2c_customer` (many-to-one).
2. `o2c_delivery -> o2c_order` (many-to-one).
3. `o2c_invoice -> o2c_delivery` (enlace proxy opcional).
4. `o2c_collection -> o2c_invoice` (many-to-one si hay clearing).

## 4) Decisiones clave de diseño

1. **Proxy contable para invoice/collection**
- Como `VBRK/VBRP/BSID/BSAD` no aparecen en el inventario actual, se define una capa canónica basada en `BKPF/BSEG`.

2. **Campos en inglés canónico**
- Evita acoplar el resto del pipeline a nombres SAP concretos.

3. **Degradación controlada**
- Entidades críticas (`o2c_order`, `o2c_delivery`) en modo fail-fast.
- Entidades de soporte (`o2c_invoice`, `o2c_collection`, `o2c_customer`) en modo soft-fail si faltan tablas.

## 5) Riesgos/limitaciones abiertas

1. Mapeo de invoice y collection seguirá siendo parcial hasta confirmar campos de billing/AR en raw.
2. Claves de negocio y deduplicación quedan para RF11-04.
3. Validaciones técnicas de null/cardinalidad quedan para RF11-06.

## 6) Validación del criterio de RF11-03

Cumplido:

1. Existe modelo canónico O2C en YAML (`config/canonical_schema_o2c.yaml`).
2. Incluye entidades, claves preliminares, relaciones y tipos.
3. Incluye definición explícita de campos obligatorios y política de degradación.

## 7) Siguiente tarea

`RF11-04` — definir business keys definitivas y estrategia de deduplicación/normalización por entidad.
