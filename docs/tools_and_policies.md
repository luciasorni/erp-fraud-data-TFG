# RF15b - Tools Registry y Políticas por Agente

## Objetivo

Definir qué tools existen, qué agente puede usar cada una y cómo se bloquean usos no autorizados
o referencias inventadas.

Implementación actual:

- `config/tools_registry.yaml`
- `config/agent_policies.yaml`
- `config/query_templates.yaml`
- `src/erp_fraud/agents/policy_enforcer.py`
- `src/erp_fraud/agents/schema_guard.py`
- `src/erp_fraud/agents/query_allowlist.py`
- `src/erp_fraud/agents/tool_call_logging.py`

## Tools disponibles

1. `DuckDBQuery`
   - Ejecución SQL solo por `query_template_id` allowlist.
   - No permite SQL libre.
2. `Schema`
   - Consulta `schema_summary` y `data_dictionary`.
3. `TestCatalog`
   - Lectura y filtrado de TestSpecs del catálogo.
4. `KBSearch`
   - Tool opcional (deshabilitada por defecto).
5. `RunStore`
   - Lectura/escritura de artefactos del run.

Fuente: `config/tools_registry.yaml`.

## Matriz Tools x Agentes

| Agente | Tools permitidas | Tools denegadas |
|---|---|---|
| `test_executor` | `DuckDBQuery`, `TestCatalog`, `Schema`, `RunStore` | `KBSearch` |
| `scorer_classifier` | `RunStore`, `Schema`, `TestCatalog` | `DuckDBQuery`, `KBSearch` |
| `expert_recommender` | `TestCatalog`, `Schema`, `RunStore` | `DuckDBQuery` |
| `explainer` | `Schema`, `RunStore` | `DuckDBQuery`, `TestCatalog`, `KBSearch` |
| `exporter` | `RunStore` | `DuckDBQuery`, `Schema`, `TestCatalog`, `KBSearch` |

Fuente: `config/agent_policies.yaml`.

## Reglas de seguridad aplicadas

1. Deny-by-default por agente (`default_policy.mode: deny_by_default`).
2. Allowlist/denylist por agente (`allowed_tools` y `denied_tools`).
3. Límites de llamadas:
   - `max_tool_calls`
   - `max_calls_per_tool`
4. Query allowlist:
   - solo `query_template_id` registrado en `config/query_templates.yaml`
   - parámetros exactos (sin parámetros extra)
5. Validación anti-alucinación (`SchemaGuard`):
   - `test_id` debe existir en catálogo
   - `table` y `column` deben existir en `schema_summary`

## Ejemplos de bloqueo

1. Tool no permitida para agente
   - ejemplo: `explainer` intentando usar `DuckDBQuery`
   - resultado: `ToolPolicyDeniedError`.
2. Tool deshabilitada en registry
   - ejemplo: `expert_recommender` intentando usar `KBSearch` con `enabled: false`
   - resultado: `ToolPolicyDeniedError`.
3. Query template no allowlist
   - ejemplo: `query_template_id = q_unknown_template`
   - resultado: `QueryTemplateNotAllowedError`.
4. Parámetros inválidos en query template
   - ejemplo: faltan requeridos o hay parámetros extra
   - resultado: `QueryTemplateValidationError`.
5. Referencias inventadas
   - ejemplo: columna o `test_id` inexistente
   - resultado: `SchemaGuardValidationError`.

## Logging de tool calls

`PolicyEnforcer.enforce_and_call(...)` registra eventos JSONL si se configura `tool_call_log_path`.

Campos principales por evento:

- `event` (`tool_call`)
- `tool_id`
- `agent_id`
- `node_id` (si aplica)
- `params_hash` (`sha256` estable de params)
- `duration_ms`
- `status` (`OK`, `ERROR`, `DENIED`)
- `error_summary` (solo en error/denegación)

## Uso mínimo

```python
from src.erp_fraud.agents import PolicyEnforcer

enforcer = PolicyEnforcer.from_yaml(
    policy_path="config/agent_policies.yaml",
    tools_registry_path="config/tools_registry.yaml",
    tool_call_log_path="run_results/demo/tool_calls.jsonl",
)

result = enforcer.enforce_and_call(
    agent_id="test_executor",
    node_id="run_tests",
    tool_id="TestCatalog",
    tool_callable=lambda **kwargs: {"ok": True},
    test_id="TST-DUPLICATE-POSTINGS",
)
```

## Tests relacionados

- `tests/test_rf15b_tools.py`
- `tests/test_rf15b_policy_and_schema_guard.py`
