# ERP Fraud Analytics (P2P) - Dossier de Presentación (histórico)

Este documento resume todo lo relevante del proyecto para explicar con confianza:
- qué problema resuelve,
- cómo está construido,
- cómo se ejecuta internamente,
- qué parte del proceso de compras cubre,
- y qué evidencias técnicas demuestran que funciona.

Puedes pasarlo completo a ChatGPT para preparar discurso, guion o diapositivas.

---

## 1) Resumen Ejecutivo

El proyecto implementa un **pipeline reproducible de analítica antifraude sobre ERP** centrado en **P2P (Procure-to-Pay)** usando el dataset `ERP Fraud Data` y `DuckDB`.

Estado actual implementado:
- RF01: ingesta reproducible
- RF02 + RF02b: diccionario y validación técnica
- RF03: catálogo inicial de tests
- RF04: motor seguro de ejecución
- RF05: salida estándar por test
- RF06: trazabilidad y drilldown
- RF07: scoring + ranking
- RF08: reporte MVP (JSON/MD/HTML)
- RF10: comando único `run` + documentación de ejecución

RF09 (batería ampliada de pruebas de software) está pendiente por decisión de planning.

---

## 2) Problema y Objetivo

### Problema
En datos ERP, detectar fraude no es solo “correr consultas”: hace falta un proceso controlado, trazable y repetible que:
- valide la calidad técnica de datos,
- ejecute controles antifraude versionados,
- priorice hallazgos,
- y permita auditoría de cada resultado.

### Objetivo del proyecto
Construir una base de producto que ejecute esa cadena end-to-end con un comando único y deje evidencia técnica de cada run.

---

## 3) Alcance Funcional Actual (P2P)

### Fuente de datos
- Input: `erp_fraud_data.zip`
- Alcance de Fase 1: `joint_datasets/` (no `raw_data/`)

### Proceso de compras (P2P) que se toma como referencia
Marco de negocio usado para explicar controles:
1. Purchase Order (PO)
2. Goods Receipt (GR)
3. Invoice
4. Payment

En esta fase, la explotación está centrada en tablas de `joint_datasets` y especialmente en los datos de facturas/asientos (`fraud_1`), sobre los que se aplican los primeros tests antifraude.

### Tipos de riesgo iniciales implementados
- Duplicados de contabilización/pago
- Importes inusuales por proveedor

---

## 4) Arquitectura (cómo está hecho)

### Capas principales
- `src/erp_fraud/ingest/`
  - lectura del zip, validación de ficheros, carga tabular, normalización de tipos, limpieza técnica.
- `src/erp_fraud/storage/`
  - DuckDB, metadata, schema summary, data validation, reportes.
- `src/erp_fraud/catalog/`
  - catálogo de tests, runner seguro, result schema, drilldown, scoring/ranking.
- `src/erp_fraud/cli/`
  - comandos operativos (`validate-dictionary`, `drilldown`, `run`).

### Artefactos por run
En `run_results/<run_id>/`:
- `ingest_logs.jsonl`
- `run_metadata.json`
- `schema_summary.json`
- `data_validation_report.json`
- `test_runner_logs.jsonl`
- `test_runs.json`
- `tests_outputs/<test_id>/...`
- `ranking.json` (+ `ranking.parquet`)
- `report.json`, `report.md`, `report.html`
- `run_structure.json` (manifiesto de estructura)

---

## 5) Proceso Interno del Pipeline (end-to-end)

Comando principal:

```bash
/opt/anaconda3/bin/python -m src.erp_fraud.cli.main run --input-zip erp_fraud_data.zip
```

Pipeline ejecutado:
1. **Ingesta**
   - localiza `joint_datasets/`
   - valida ficheros esperados
   - carga CSV/Parquet robustamente
2. **Normalización / limpieza técnica**
   - fechas/importes/IDs
   - trim y nulls técnicos
3. **Carga en DuckDB**
   - tablas en `erp.duckdb`
   - métricas por tabla
4. **Trazabilidad de datos**
   - `dataset_hash`
   - `schema_summary.json`
   - `run_metadata.json`
5. **Validación técnica previa (RF02b)**
   - columnas requeridas
   - parseos críticos
   - nulos/rangos (warnings)
6. **Ejecución segura de tests (RF04)**
   - solo allowlist de catálogo
   - manejo `ERROR/TIMEOUT`
7. **Output estándar por test (RF05)**
   - `entity_key`, `keys`, `evidence_columns`, `metrics`
8. **Agregación y ranking (RF07)**
   - `score_test = weight * metric`
   - agregación por entidad
9. **Reporte MVP (RF08)**
   - `report.json`, `report.md`, `report.html`
   - validación de links de artefactos

---

## 6) Catálogo de Tests y Ejecución Segura

### Catálogo versionado
- `tests/catalog/tst_duplicate_postings.yaml`
- `tests/catalog/tst_unusual_amount_by_vendor.yaml`

### Principio de seguridad
- No hay SQL libre en runtime del usuario.
- Solo se ejecutan tests definidos en catálogo (allowlist).
- Drilldown usa plantillas seguras parametrizadas.

---

## 7) Proceso de Compra (P2P) explicado para defensa

Cómo conectar negocio y técnica al exponer:
- El pipeline no “adivina fraude”: ejecuta **controles concretos** sobre eventos del ciclo P2P.
- En esta fase, los controles se centran en la parte de facturas/contabilizaciones:
  - detectar duplicidades (riesgo de pago duplicado),
  - detectar importes atípicos por proveedor (riesgo de manipulación o anomalía).
- El diseño está preparado para crecer hacia más controles del flujo completo PO-GR-Invoice-Payment con el mismo marco técnico.

---

## 8) Reproducibilidad, Trazabilidad y Evidencia

### Reproducibilidad
- hashing del dataset (`dataset_hash`)
- orden estable en outputs y ranking
- estructura de run fija (`run_structure.json`)

### Trazabilidad
- del ranking al detalle vía `entity_key` y `keys`
- drilldown bidireccional a filas origen en DuckDB
- logs estructurados y artefactos por fase

### Evidencia de aceptación (ejemplos)
- RF07: `run_results/rf07-08-verification-20260310/`
- RF08: `run_results/rf08-10-verification-20260310/`
- RF10: `run_results/rf10-08-verification-20260310/`

---

## 9) Decisiones Técnicas Clave y Trade-offs

1. **DuckDB local**
   - Pro: simple, rápido para analítica local y reproducible.
   - Contra: no orientado a concurrencia de servicio productivo multiusuario.
2. **Catálogo YAML de tests**
   - Pro: versionable y auditado.
   - Contra: más rigidez que un motor de consultas ad hoc.
3. **Bloqueo por críticos en validación técnica**
   - Pro: evita ejecutar analítica sobre datos inválidos.
   - Contra: requiere buen mantenimiento de reglas/umbrales.
4. **Reporte JSON + MD/HTML**
   - Pro: máquina + humano.
   - Contra: más componentes de mantenimiento.

---

## 10) Cómo demostrarlo en una demo (guion corto)

1. Ejecutar comando único:
   - `make run INPUT_ZIP=erp_fraud_data.zip RUN_ID=demo-tfg`
2. Mostrar estructura generada:
   - `run_results/demo-tfg/run_structure.json`
3. Enseñar ranking:
   - `run_results/demo-tfg/ranking.json`
4. Enseñar reporte:
   - `report.md` y `report.html`
5. Hacer drilldown de un hallazgo:
   - comando `drilldown --run-id ... --test-id ... --entity-key ...`

Mensaje clave:
- “No solo detecto, también puedo explicar y reconstruir por qué salió cada hallazgo”.

---

## 11) Preguntas 

### ¿Cómo sé que no inventa hallazgos?
Porque la ejecución es determinista, basada en catálogo y SQL/Python controlado; además cada hallazgo tiene `keys` y drilldown a origen.

### ¿Cómo controlas errores?
Hay validación técnica previa (críticos vs warning), captura de errores por test, continuidad del run y reporte de errores.

### ¿Qué pasaría al escalar a más empresas?
El diseño separa catálogo, reglas, validación y reporting; siguiente paso natural: mapeo configurable (RF12).

### ¿Qué limita ahora el sistema?
Cobertura actual de tests (fase inicial), dependencia de calidad del dataset y falta de CI completa (RF09 pendiente).

---

## 12) Referencias internas para profundizar

- `README.md`
- `docs/architecture.md`
- `docs/data.md`
- `docs/how_to_run.md`
- `docs/tests.md`
- `docs/rf07.md`
- `docs/rf08.md`
- `docs/rf10.md`

---

