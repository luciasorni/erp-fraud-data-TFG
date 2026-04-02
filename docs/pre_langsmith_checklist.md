# Pre-LangSmith Checklist (RF14b)

Checklist obligatorio antes de activar LangSmith y pasar a cloud.

## 1) Contratos y compatibilidad

- [x] `GraphState` versionado y documentado (campos obligatorios + opcionales).
- [x] `ExplanationSchema` y `ScoreSchema` congelados (version + required fields).
- [x] Test de compatibilidad retro de artefactos (`report.json`, `explanation.json`, `score.json`).

## 2) Configuración única

- [x] Un único loader de config para run/nodos/modelos.
- [x] Defaults centralizados (sin valores duplicados repartidos por nodos).
- [x] Validación de config al arranque (`scripts/validate_project_schema.py`).

## 3) Observabilidad local homogénea

- [x] Logs estructurados con `run_id`, `node_id`, `phase`, `status`, `duration_ms`.
- [x] Métricas por nodo persistidas en `run_metadata` (`retries`, `timeouts`, `errors`).
- [x] Taxonomía de errores estable (`VALIDATION_ERROR`, `TIMEOUT`, `TOOL_DENIED`, etc.).

## 4) Calidad y release gate

- [x] Comando único de regresión pre-release (subset RF14/RF15/RF15c/RF18).
- [x] Snapshots "golden" de outputs críticos activos y en verde.
- [x] CI ejecuta el gate sin `--no-verify`.

## 5) Seguridad y secretos

- [x] `env.example` actualizado con variables necesarias (sin secretos reales).
- [x] Política de secretos documentada (local + CI + cloud).
- [x] Fallo controlado si falta variable requerida.

## 6) Cloud-readiness mínima

- [x] Capa de rutas desacoplada de filesystem local (preparada para object storage).
- [x] Artefactos del run con naming estable (`run_results/<run_id>/...`).
- [x] Documentación de precondiciones cloud antes de RF14c.

## Resultado esperado para arrancar RF14b

Se puede trazar en LangSmith sin ambigüedad de contratos, con salidas reproducibles y errores diagnósticables.

## Evidencia (RF14b-P06)

- Contratos + compatibilidad retro:
  - `tests/test_rf14b_contracts.py`
  - `tests/fixtures/contracts/report_v1_min.json`
- Config centralizada:
  - `src/erp_fraud/config/run_defaults.py`
  - `src/erp_fraud/cli/main.py`
  - `src/erp_fraud/graph/nodes/deps.py`
- Observabilidad + taxonomy:
  - `src/erp_fraud/graph/observability.py`
  - `src/erp_fraud/graph/graph.py`
- Release gate:
  - `scripts/run_pre_langsmith_gate.py`
  - `Makefile` (`make pre-langsmith-gate`)
  - `.github/workflows/ci.yml`
- Secretos baseline:
  - `.env.example`
  - `scripts/validate_required_env.py`
