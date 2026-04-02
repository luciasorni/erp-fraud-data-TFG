# Legacy Migration Map

## Estado final
La migración legacy está **cerrada**: `src/erp_fraud/graph/nodes/_legacy.py` fue eliminado.
No hay imports de `_legacy` en código operativo ni en tests.

## Mapa actual (fuente de verdad)

### Nodos operativos (nuevos)
- `src/erp_fraud/graph/nodes/planning.py`
  - `hypothesis_planner_node`
  - `test_planner_node`
- `src/erp_fraud/graph/nodes/ingest.py`
  - `ingest_node`
  - `kb_index_node`
- `src/erp_fraud/graph/nodes/executor.py`
  - `executor_node`
- `src/erp_fraud/graph/nodes/explainer.py`
  - `explainer_node`
  - `expert_explainer_node`
- `src/erp_fraud/graph/nodes/scoring.py`
  - `scoring_node`
- `src/erp_fraud/graph/nodes/persist.py`
  - `persist_node`
- Dispatcher:
  - `src/erp_fraud/graph/nodes/registry.py` (`run_node_by_id`)

### Sustitución por módulos estables
- `src/erp_fraud/graph/nodes/deps.py`
  - dependencias parcheables para tests/runtime (`KBSearchTool`, `TestRunner`, `alpha_loop`, `build_kb_index`, `tool_test_catalog`)
- `src/erp_fraud/graph/nodes/alpha_runtime.py`
  - runtime Alpha/LLM + re-export de helpers comunes
- `src/erp_fraud/graph/nodes/tooling.py`
  - policy enforcer + tools de esquema/data catalog/runstore
- `src/erp_fraud/graph/nodes/finding_utils.py`
  - helpers de hipótesis/compatibilidad schema/resultados/explanations
- `src/erp_fraud/graph/nodes/validators.py`
  - validadores de hipótesis/tests/explanations/scores
- `src/erp_fraud/graph/nodes/io_utils.py`
  - persistencia y paths de run

## Resultado
- Nodos de negocio (`planning`, `ingest`, `executor`, `explainer`, `scoring`, `persist`) desacoplados del legacy.
- Compat de monkeypatch preservada vía `deps.py`.
- Pipeline de calidad estable:
  - `ruff check src/erp_fraud/graph/nodes`
  - `pytest -q` en verde.

## Criterio de “legacy cerrado”
- Ningún módulo nuevo usa `globals().update(...)` ni `_legacy`.
- `registry.py` y `__init__.py` no dependen de `_legacy` para lógica operativa.
- Suite completa y run real pasan sin fallback inesperado.
