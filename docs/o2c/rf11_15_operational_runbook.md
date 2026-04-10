# RF11-15 — Runbook Operativo O2C (CLI + Graph/Agents)

## 1) Objetivo

Dejar operativo O2C con comandos reproducibles para:

1. run determinista de datos O2C,
2. run de grafo (LangGraph + agentes) en `stub` y `real`,
3. trazabilidad en LangSmith cuando `llm_mode=real`.

Prerequisito de entorno para autoload O2C desde `raw_data/*.zip`:

- `openpyxl` instalado en el entorno Python activo (lectura de tablas SAP en `.XLSX`).

## 1.1 Aclaración de arquitectura (importante)

Hay **dos planos de ejecución** complementarios:

1. `erp-fraud run --process-family o2c` (CLI base determinista):
   - intenta auto-cargar tablas SAP raw O2C desde `erp_fraud_data/raw_data/*.zip` dentro de `--input-zip` hacia `main` en DuckDB (priorizando tablas requeridas de entidades `fail_fast`),
   - construye canónico O2C,
   - ejecuta validación técnica O2C,
   - genera reporte técnico/artefactos base.
2. `scripts/run_rf15c_e2e_manual.py --process-family o2c` (grafo/agentes):
   - ejecuta nodos/agentes (`hypothesis_planner`, `test_planner`, `executor`, `expert_explainer`, `scoring`, `persist`),
   - permite `llm_mode=stub|real`,
   - integra AlphaCodium loop + LangGraph + LangSmith.

No son caminos contradictorios: el primero prepara/valida datos O2C; el segundo ejecuta detección multiagente y explicabilidad.

## 2) O2C determinista (pipeline base)

```bash
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --db-path erp.duckdb \
  --process-family o2c \
  --o2c-canonical-schema-config config/canonical_schema_o2c.yaml \
  --o2c-identity-config config/o2c_entity_identity.yaml \
  --o2c-mapping-config config/column_mapping_o2c.yaml \
  --o2c-target-schema o2c \
  --run-id rf11-o2c-cli
```

## 3) O2C grafo/agentes en modo stub

```bash
python3 scripts/run_rf15c_e2e_manual.py \
  --run-id rf11-o2c-graph-stub \
  --schema-summary-path run_results/rf11-o2c-cli/schema_summary.json \
  --catalog-path tests/catalog_o2c \
  --persist-base-dir run_results \
  --process-family o2c \
  --db-path erp.duckdb \
  --schema-name o2c \
  --table-name o2c_order \
  --llm-mode stub
```

## 4) O2C grafo/agentes en modo real (OpenAI + LangSmith)

```bash
set -a; source .env; set +a
python3 scripts/run_rf15c_e2e_manual.py \
  --run-id rf11-o2c-graph-real \
  --schema-summary-path run_results/rf11-o2c-cli/schema_summary.json \
  --catalog-path tests/catalog_o2c \
  --persist-base-dir run_results \
  --process-family o2c \
  --db-path erp.duckdb \
  --schema-name o2c \
  --table-name o2c_order \
  --hypothesis-max-items 4 \
  --test-planner-top-n 4 \
  --test-planner-min-per-hypothesis-real 1 \
  --llm-mode real
```

Variables requeridas:

- `OPENAI_API_KEY`
- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `LANGSMITH_ENDPOINT`
- `LANGSMITH_TRACING=true` (o `LANGCHAIN_TRACING_V2=true`)

## 5) Verificación rápida de salida

```bash
python3 scripts/show_run_summary.py --run-id rf11-o2c-graph-real
```

Comprobar en `run_results/<run_id>/graph/graph_state.json`:

- `run_metadata.process_family=o2c`
- `run_metadata.llm_mode=real`
- `run_metadata.llm_runtime_by_node.*.status=OK` en nodos LLM
- `run_metadata.langsmith_trace_link` no vacío (si credenciales válidas)

Comprobar en `run_results/<run_id>/run_metadata.json` (run CLI O2C):

- `o2c_raw_autoload.status` (`OK|PARTIAL|SKIPPED`)
- `o2c_raw_autoload.tables_loaded`
- `o2c_raw_autoload.target_tables`
- `o2c_optional_placeholders_created`

## 6) Scope de catálogo O2C operativo

Catálogo ejecutable actual:

- `TST-O2C-PRICE-OUTLIER`
- `TST-O2C-DISCOUNT-POLICY-BREACH`
- `TST-O2C-DELIVERY-QUANTITY-MISMATCH`
- `TST-O2C-NEGATIVE-DELIVERY-QUANTITY`
- `TST-O2C-CLEARING-ANOMALY`
- `TST-O2C-INVOICE-AMOUNT-ANOMALY`
- `TST-O2C-INVOICE-DATE-SEQUENCE`

Ubicación:

- `tests/catalog_o2c/`
