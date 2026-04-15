# ERP Fraud Analytics (P2P) - Dossier de Presentación (Actualizado)

Este documento resume el estado actual del proyecto para explicarlo con confianza:
- qué problema resuelve,
- cómo está construido hoy,
- cómo se ejecuta internamente,
- qué hace cada agente,
- qué herramientas se usan y cómo afectan al sistema,
- y qué queda pendiente (AWS/O2C).

---

## 1) Resumen Ejecutivo

El proyecto es una plataforma híbrida de analítica antifraude ERP:
- base determinista y reproducible (ingesta, validación, tests, ranking, reporte),
- más una capa multiagente con LLM orquestada por LangGraph.

Estado implementado relevante:
- RF01-RF08, RF10, RF13
- RF14 (grafo multiagente)
- RF14b (trazabilidad/evaluación con LangSmith)
- RF15 (explicaciones con guardrails)
- RF15b (tools/policies/schema guard)
- RF15c (flujo multiagente integrado, `llm_mode=stub|real`)
- RF15e (KB local con Chroma)
- RF18 (scoring robusto con contrato)

Pendiente explícito:
- RF14c cloud/AWS (pendiente)
- O2C (pendiente; foco actual en P2P)

---

## 2) Problema y Objetivo

### Problema
Detectar fraude en ERP requiere algo más que consultas sueltas:
- control de calidad de datos,
- controles versionados y seguros,
- priorización de hallazgos,
- explicabilidad auditable,
- trazabilidad completa del run.

### Objetivo
Ejecutar el ciclo end-to-end de forma reproducible y auditable, con evidencia técnica por run.

---

## 3) Alcance Funcional Actual (P2P)

### Fuente de datos
- Input: `erp_fraud_data.zip`
- Alcance operativo: `joint_datasets/` (no `raw_data/`)

### Proceso de negocio referenciado
1. Purchase Order (PO)
2. Goods Receipt (GR)
3. Invoice
4. Payment

Foco actual de explotación: facturas/asientos sobre tablas de `joint_datasets`.

### Riesgos implementados (estado actual)

Actualmente hay **8 tests implementados** en catálogo, que cubren estas tipologías:
- `duplicate_payment`
- `duplicate_entry`
- `amount_anomaly`
- `authorization_bypass` (cubierta por 2 tests)
- `inventory_anomaly`
- `suspicious_payment_pattern`
- `invoice_number_anomaly`

---

## 4) Arquitectura (cómo está hecho)

### Capas principales
- `src/erp_fraud/ingest/`
  - lectura zip, validación, carga tabular, normalización y limpieza técnica.
- `src/erp_fraud/storage/`
  - DuckDB, metadata, schema summary, validación técnica, reporting.
- `src/erp_fraud/catalog/`
  - catálogo de tests, runner seguro, result schema, drilldown, scoring/ranking.
- `src/erp_fraud/agents/`
  - policy enforcer, schema guard, query allowlist, logging tools, KB.
- `src/erp_fraud/graph/`
  - `state.py`, `graph.py`, y nodos modulares (`nodes/`).
- `src/erp_fraud/cli/`
  - comandos operativos.

### Artefactos por run
En `run_results/<run_id>/`:
- `run_metadata.json`, `schema_summary.json`, `data_validation_report.json`
- `test_runs.json`, `test_runner_logs.jsonl`, `tests_outputs/<test_id>/...`
- `ranking.json`
- `report.json`, `report.md`, `report.html`
- `graph/graph_state.json`, `graph/hypotheses.json`, `graph/selected_tests.json`, `graph/findings.json`, `graph/explanations.json`, `graph/scores.json`

---

## 5) Flujo interno end-to-end

Comando base:

```bash
python3 -m src.erp_fraud.cli.main run --input-zip erp_fraud_data.zip
```

Pipeline:
1. Ingesta y carga DuckDB
2. Validación técnica previa
3. Ejecución segura de tests de catálogo
4. Salidas estandarizadas por test
5. Agregación/ranking
6. Reporte final

Flujo multiagente (RF14/RF15c):
1. `hypothesis_planner`
2. `test_planner`
3. `executor`
4. `expert_explainer`
5. `scoring`
6. `persist`

---

## 5.1 Flujo real completo (de principio a final)

Esta es la secuencia real que sigue el proyecto en operación, en orden cronológico:

### A) Preparación de ejecución

1. Se carga configuración (`.env`, `config/*.yaml`, argumentos CLI).
2. Se define `run_id` y estructura de salida `run_results/<run_id>/`.
3. Se registra metadata inicial del run (modo LLM, rutas, versiones, flags activas).

### B) Ingesta y preparación de datos (determinista)

1. Se abre `erp_fraud_data.zip`.
2. Se localiza `joint_datasets/` y se validan ficheros esperados.
3. Se cargan CSV/Parquet con parseos robustos.
4. Se normalizan tipos (fechas, importes, IDs) y limpieza técnica mínima.
5. Se persiste en DuckDB local (`erp.duckdb`).
6. Se genera:
   - `dataset_hash` (reproducibilidad),
   - `schema_summary.json`,
   - logs de ingesta.

### C) Validación técnica previa (determinista)

1. Se extraen columnas requeridas desde catálogo de tests.
2. Se comprueba:
   - columnas faltantes (crítico),
   - errores de parseo (crítico),
   - nulos/rangos básicos (warning).
3. Se guarda `data_validation_report.json`.
4. Regla:
   - si hay críticos -> se bloquea el run,
   - si hay solo warnings -> continúa.

### D) Orquestación LangGraph (núcleo multiagente)

LangGraph crea/actualiza `GraphState` y ejecuta nodos en cadena:

1. **`hypothesis_planner` (LLM)**
   - construye hipótesis iniciales de fraude.
   - salida: `hypotheses.json`.

2. **`test_planner` (LLM)**
   - selecciona tests del catálogo para validar hipótesis.
   - enforce de allowlist + compatibilidad schema.
   - salida: `selected_tests.json`.

3. **`executor` (determinista)**
   - ejecuta tests reales con `TestRunner` sobre DuckDB.
   - maneja `OK/ERROR/TIMEOUT` por test sin romper run completo.
   - salida: `findings.json` + `tests_outputs/<test_id>/...`.

4. **`expert_explainer` (LLM)**
   - genera explicación de hallazgos con evidencia concreta.
   - aplica guardrails anti-invención (test_id/columnas/keys reales).
   - si falla validación, repara (loop) y reintenta.
   - salida: `explanations.json`.

5. **`scoring` (LLM + contrato)**
   - integra evidencia y emite clasificación final:
     - `final_label`
     - `confidence`
     - `fraud_type_probs`
   - valida contra `ScoreSchema`.
   - salida: `scores.json`.

6. **`persist` (determinista)**
   - persiste estado final del grafo y manifiestos.
   - salida: `graph/graph_state.json` + artefactos finales.

### E) Guardrails durante el flujo

En nodos LLM y tools:

1. `PolicyEnforcer`: bloquea tools no autorizadas.
2. `SchemaGuard`: bloquea referencias no existentes (test/tabla/columna).
3. Query allowlist: impide SQL libre.
4. AlphaCodium loop (`plan -> draft -> validate -> repair`) para robustecer salida.
5. Fallback seguro:
   - si falla LLM o validación tras reintentos, cae a ruta controlada sin abortar el run entero.

### F) Observabilidad y trazabilidad

Durante la ejecución se registra:

1. `run_metadata["node_trace_events"]`:
   - nodo, estado, duración, errores.
2. `run_metadata["llm_runtime_by_node"]`:
   - modelo usado, tokens, latencia, coste estimado, retries, fallback.
3. Si LangSmith está activo:
   - publicación de trazas y `trace_link`.

### G) Cierre del run y consumo funcional

Al final, el sistema produce:

1. Artefactos técnicos por fase.
2. Reporte final (`report.json`, `report.md`, `report.html`).
3. Ranking de entidades sospechosas.
4. Drilldown reproducible por `entity_key`.

Uso en defensa:

1. Enseñar `show_run_summary`.
2. Abrir `graph_state.json` (estado de nodos, LLM runtime, trazas).
3. Abrir `report.md` para lectura ejecutiva.
4. Abrir `findings/explanations/scores` para justificar decisión final.

---

## 6) Papel de cada agente

## 6.1 `hypothesis_planner` (LLM)
- Genera hipótesis de fraude iniciales.
- Usa prompt versionado + validación estructurada.

## 6.2 `test_planner` (LLM)
- Selecciona tests del catálogo para cada hipótesis.
- Respeta allowlist y compatibilidad de schema.

## 6.3 `executor` (determinista, no LLM)
- Ejecuta los tests reales sobre datos.
- Maneja errores/timeouts sin romper el run completo.

## 6.4 `expert_explainer` (LLM)
- Explica hallazgos con evidencia auditable.
- Guardrails anti-invención y reparación si hay errores.

## 6.5 `scoring` (LLM + contrato)
- Emite tipología final (`final_label`) y confianza.
- Valida `ScoreSchema`, retries y fallback controlado.

## 6.6 `persist` (determinista)
- Guarda estado, artefactos, trazas y manifest del run.

---

## 7) LLM: cómo se usa realmente

El LLM funciona en producción local, pero **no como chat**.
Se usa como motor interno de nodos con:
- entradas estructuradas,
- validación automática,
- guardrails de seguridad/consistencia,
- y fallback controlado.

Modos:
- `llm_mode=stub`: determinista, barato y estable para CI.
- `llm_mode=real`: proveedor real (OpenAI) para runs operativos.

---

## 8) Herramientas usadas y para qué sirven

1. **DuckDB**
- Motor analítico local para tests y drilldown.

2. **LangGraph**
- Orquesta el flujo de nodos y estado compartido.

3. **OpenAI**
- LLM en nodos `hypothesis_planner`, `test_planner`, `expert_explainer`, `scoring` (modo real).

4. **LangSmith**
- Trazabilidad de runs reales, comparación y observabilidad.

5. **AlphaCodium loop**
- Ciclo plan/draft/validate/repair para robustez de salidas LLM.

6. **ChromaDB (RF15e)**
- KB local para indexado y recuperación de contexto.

7. **PolicyEnforcer + SchemaGuard + Query Allowlist**
- Seguridad: sin SQL libre, sin tools no permitidas, sin referencias inventadas.

---

## 9) Seguridad, Trazabilidad y Reproducibilidad

- Sin SQL libre en runtime.
- Ejecución solo desde catálogo allowlist.
- Validación técnica bloquea errores críticos.
- Contratos de salida (`ResultSchema`, `ExplanationSchema`, `ScoreSchema`).
- Hash y artefactos estables por run.
- Trazabilidad por nodo en `run_metadata`.

---

## 10) Evidencia de funcionamiento real

Indicadores de run real correcto:
- `graph_status=OK`
- `llm_mode=real`
- `llm_runtime_by_node` con nodos en `status=OK`
- `langsmith_runs.status=OK` y `trace_link` válido (si LangSmith activo)

Baseline real de referencia:
- `run_id`: `real-check-20260402-154238`

---

## 11) Demo rápida (guion)

1. Ejecutar run real:

```bash
set -a; source .env; set +a
python3 scripts/run_rf15c_e2e_manual.py \
  --run-id demo-real \
  --schema-summary-path run_results/rf10-08-acceptance-run/schema_summary.json \
  --catalog-path tests/catalog \
  --persist-base-dir run_results \
  --llm-mode real
```

2. Mostrar resumen:

```bash
python3 scripts/show_run_summary.py --run-id demo-real
```

3. Enseñar trazabilidad:
- `run_results/demo-real/graph/graph_state.json`
- `run_results/demo-real/report.md`

---

## 12) Pendientes y próximos pasos

1. RF14c cloud/AWS (pendiente)
2. Extensión de alcance O2C (pendiente)
3. Mayor cobertura de tests/familias de fraude
4. Hardening final productivo en cloud

---

## 13) Referencias internas

- `README.md`
- `docs/how_to_run.md`
- `docs/langgraph_architecture.md`
- `docs/agents.md`
- `docs/rf14.md`
- `docs/rf14b.md`
- `docs/rf14b_verification.md`
- `docs/rf15.md`
- `docs/rf15c.md`
- `docs/scoring.md`
- `docs/rag_kb.md`
