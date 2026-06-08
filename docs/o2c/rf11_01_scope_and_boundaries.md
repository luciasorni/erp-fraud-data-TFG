# RF11-01 — Alcance O2C y Límites de Fase

Fecha: 2026-04-09  
Estado: Definido

## 1) Contexto

El proyecto actual está implementado y verificado para P2P.  
RF11 abre la extensión a O2C usando `raw_data` del dataset `erp_fraud_data`.

Esta tarea (`RF11-01`) **no implementa lógica nueva de ejecución**.  
Su objetivo es fijar alcance y límites para evitar deriva de diseño.

## 2) Definición O2C para esta fase

Cadena O2C considerada:

1. `Sales Order` (pedido de venta)
2. `Delivery / Fulfillment` (entrega)
3. `Invoice` (facturación)
4. `Collection / Cash Application` (cobro y aplicación)

Referencia funcional de desviaciones de fraude (P2P/O2C):

- `docs/o2c/rf11_process_fraud_reference.md`

## 3) Alcance funcional (IN)

Incluido en RF11 (fase actual):

- Diseñar modelo canónico mínimo O2C (entidades y claves).
- Mapear `raw_data` a entidades O2C canónicas.
- Habilitar ejecución O2C en el pipeline sin romper P2P.
- Mantener artefactos estándar (`findings`, `ranking`, `report`, `graph/*`).
- Trazabilidad por familia de proceso (`process_family: p2p|o2c`).

Entidades canónicas mínimas objetivo:

- `o2c_order`
- `o2c_delivery`
- `o2c_invoice`
- `o2c_collection`
- `o2c_customer` (mínima, si datos disponibles)

## 4) Fuera de alcance (OUT)

No incluido en esta fase:

- Rehacer arquitectura completa o duplicar pipeline.
- Integración cloud/AWS.
- Modelado maestro completo multientidad (MDM avanzado).
- Cobertura total de todos los escenarios O2C posibles.
- Reentrenamiento/modelado ML.
- Cambios destructivos en contratos P2P ya estables.

## 5) Principios de implementación

1. Reutilización máxima:
- Reusar orquestación del grafo multiagente propio, persistencia, reporting, guardrails, scoring y trazabilidad existentes.

2. Compatibilidad hacia atrás:
- P2P debe seguir funcionando con los mismos comandos/artefactos esperados.

3. Aislamiento de cambios:
- Cambios O2C introducidos por configuración/flags y capas nuevas (mapping/modelo), no por bifurcación caótica.

4. Validación incremental:
- Cada tarea RF11 se cierra con verificación focalizada + smoke de regresión P2P.

## 6) Dependencia de datos

Fuente para O2C:

- `erp_fraud_data/raw_data` (no `joint_datasets`).

Implicación:

- Se requiere etapa explícita de preparación/modelado (`raw -> canónico O2C`) previa a tests O2C.

## 7) Riesgos identificados

1. Cobertura real de campos O2C en raw puede ser incompleta o inconsistente.
2. Riesgo de acoplar O2C a supuestos P2P si no se separa por `process_family`.
3. Riesgo de romper regresión P2P al tocar ingest/orquestación.

Mitigación base:

- Inventario de columnas temprano,
- mapping explícito versionado,
- test de regresión cruzada P2P vs O2C.

## 8) Criterios de aceptación de RF11-01

Se considera cerrada esta tarea cuando:

1. Existe este documento con alcance/límites explícitos.
2. Está documentada la cadena O2C objetivo y sus entidades mínimas.
3. Queda claro qué está fuera de alcance.
4. Se fija estrategia de reutilización y compatibilidad P2P.

## 9) Próxima tarea

Siguiente paso técnico: `RF11-02`  
Inventario de tablas/columnas `raw_data` relevantes para O2C y correspondencia preliminar.
