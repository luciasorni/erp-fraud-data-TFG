# Prompts Versionados (AG03-03)

Convención de nombres:

- `agent_name__vNNN.md`
- ejemplo: `hypothesis_planner__v001.md`

Reglas:

1. No sobrescribir versiones antiguas.
2. Si cambia el contenido, crear nueva versión (`v002`, `v003`, ...).
3. Mantener compatibilidad con constraints de seguridad:
   - allowlist de tools
   - no inventar tablas/columnas/test_id
   - no SQL libre

Prompts iniciales:

- `hypothesis_planner__v001.md`
- `test_planner__v001.md`
- `expert_explainer__v001.md`
- `scoring__v001.md`
