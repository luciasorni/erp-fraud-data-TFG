# O2C Docs

Documentación específica de la extensión O2C (Order-to-Cash) del proyecto.

## Objetivo

Centralizar decisiones y evidencias de RF11 para no mezclar contexto P2P y O2C.

## Contenido

- `docs/o2c/rf11_01_scope_and_boundaries.md`
  - alcance funcional de O2C para esta fase,
  - límites explícitos (qué no entra todavía),
  - dependencias de datos `raw_data`,
  - criterios de aceptación de RF11-01.
- `docs/o2c/rf11_02_raw_inventory.md`
  - inventario reproducible de tablas en `raw_data`,
  - cobertura de tablas O2C candidatas por dataset,
  - gaps detectados y decisión técnica para modelado canónico.
- `docs/o2c/rf11_process_fraud_reference.md`
  - mapa funcional de desviaciones de fraude P2P/O2C a partir de proceso de negocio,
  - traducción a señales analíticas y su impacto en RF11-03+.
- `docs/o2c/rf11_03_canonical_schema.md`
  - definición del modelo canónico O2C (entidades, relaciones, campos obligatorios/opcionales),
  - decisiones de degradación controlada por disponibilidad de tablas raw.
- `docs/o2c/rf11_04_business_keys_and_dedup.md`
  - definición de business keys por entidad O2C,
  - reglas de normalización y estrategia declarativa de deduplicación.
- `docs/o2c/rf11_05_raw_to_canonical_transform.md`
  - implementación base de transformación `raw -> canónico O2C` en DuckDB,
  - script manual de ejecución y cobertura de tests RF11-05.
- `docs/o2c/rf11_06_o2c_technical_validation.md`
  - validaciones técnicas sobre tablas canónicas O2C (required/null/parse/cardinalidad),
  - script manual de ejecución y cobertura de tests RF11-06.
- `docs/o2c/rf11_07_process_family_integration.md`
  - integración del selector `process_family` (`p2p|o2c`) en configuración/CLI/metadata,
  - separación explícita de runs por familia de proceso.
- `docs/o2c/rf11_08_orchestration_process_family.md`
  - adaptación de orquestación `run` para rama O2C sin romper rama P2P,
  - flags O2C y artefactos de run en modo O2C.
- `docs/o2c/rf11_09_column_mapping.md`
  - mapping explícito `raw -> canónico O2C` con casts/defaults controlados,
  - integración del mapping en CLI y runtime de transformación.
- `docs/o2c/rf11_10_o2c_data_dictionary.md`
  - data dictionary O2C mínimo generado desde schema + mapping,
  - artefactos JSON/MD para trazabilidad funcional-técnica.
- `docs/o2c/rf11_11_o2c_hypothesis_matrix.md`
  - matriz O2C hipótesis->tests->evidencia para base planner/explainer,
  - validación automática de consistencia contra schema/identity.
- `docs/o2c/rf11_12_o2c_fraud_taxonomy.md`
  - alineación de `fraud_type` O2C con Fraud Tree oficial,
  - validación automática de cobertura de mapping.
- `docs/o2c/rf11_13_o2c_integration_tests.md`
  - inventario y criterio de tests de integración O2C,
  - verificación E2E de persistencia de artefactos y reporte.
- `docs/o2c/rf11_14_cross_process_regression.md`
  - regresión cruzada P2P vs O2C para controlar no-regresión funcional,
  - script único de evidencia de checks.
- `docs/o2c/rf11_15_operational_runbook.md`
  - comandos operativos O2C para CLI y grafo/agentes en `stub|real`,
  - checklist de variables OpenAI/LangSmith y validación de salida.
- `docs/o2c/rf11_16_final_verification.md`
  - cierre de verificación RF11 con evidencias y riesgos abiertos,
  - criterio final de aceptación de requisito.
- `docs/o2c/artifacts/rf11_02_raw_inventory.json`
  - evidencia máquina del inventario (datasets, tablas y cobertura).
- `docs/o2c/artifacts/rf11_10_o2c_data_dictionary.json`
- `docs/o2c/artifacts/rf11_10_o2c_data_dictionary.md`
- `docs/o2c/artifacts/rf11_11_o2c_hypothesis_matrix.csv`
- `docs/o2c/artifacts/rf11_11_o2c_hypothesis_matrix.md`
- `docs/o2c/artifacts/rf11_12_o2c_taxonomy_validation.json`

## Regla de trabajo

Cada tarea RF11 cerrada debe dejar:

1. decisión de diseño,
2. impacto en código/config,
3. cómo se valida,
4. riesgos abiertos.
