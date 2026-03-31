# RF15b - Estado

## Alcance

Definir tools disponibles, políticas por agente/nodo y validaciones para bloquear:

- uso de tools no permitidas,
- SQL libre fuera de allowlist,
- referencias inventadas de tabla/columna/test.

## Implementación completada

Configuración:

- `config/tools_registry.yaml`
- `config/agent_policies.yaml`
- `config/query_templates.yaml`

Runtime:

- `src/erp_fraud/agents/policy_enforcer.py`
- `src/erp_fraud/agents/schema_guard.py`
- `src/erp_fraud/agents/query_allowlist.py`
- `src/erp_fraud/agents/tool_call_logging.py`

Documentación:

- `docs/tools_and_policies.md`

## Verificación

Suite RF15b:

```bash
/opt/anaconda3/bin/python -m pytest -q \
  tests/test_rf15b_tools.py \
  tests/test_rf15b_policy_and_schema_guard.py \
  tests/test_rf15b_tool_call_logging.py
```

Resultado actual: `14 passed`.

## Comportamiento de seguridad

- Deny-by-default por agente.
- Allowlist/denylist de tools por agente.
- Límites de llamadas por agente y por tool.
- Query execution solo por `query_template_id` permitido.
- `SchemaGuard` valida existencia real de `test_id`, tabla y columna.
- Logging estructurado por tool call: `OK`, `DENIED`, `ERROR`.
