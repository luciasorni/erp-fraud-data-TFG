# Testing

Este documento resume las suites útiles para revisión externa. El registro completo de integración está en `docs/integration_tests_registry.md`.

## Entorno

Instalación recomendada:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

El CI usa Python 3.11 (`.github/workflows/ci.yml`). El contenedor batch usa Python 3.9 (`Dockerfile`).

## Smoke test mínimo

```bash
python3 -m src.erp_fraud.cli.main run --help
python3 -m pytest -q tests/test_rf20_api.py tests/test_rf20_ui_utils.py
```

## API/UI

```bash
python3 -m pytest -q \
  tests/test_rf20_api.py \
  tests/test_rf20_services.py \
  tests/test_rf20_ui_api_client.py \
  tests/test_rf20_ui_utils.py
```

Valida contrato HTTP base, servicios de runs/datasets/resultados, cliente Streamlit y utilidades de presentación.

## Pipeline base

```bash
python3 -m pytest -q \
  tests/test_rf01_ingest_storage.py \
  tests/test_rf02_data_dictionary.py \
  tests/test_rf02b_data_validation.py \
  tests/test_rf03_catalog.py \
  tests/test_rf04_runner.py \
  tests/test_rf05_result_schema_and_writer.py \
  tests/test_rf06_drilldown.py tests/test_rf06_drilldown_components.py \
  tests/test_rf07_ranking.py \
  tests/test_rf08_reporting.py
```

## O2C

```bash
python3 -m pytest -q \
  tests/test_rf11_o2c_cli_run.py \
  tests/test_rf11_o2c_transform.py \
  tests/test_rf11_o2c_validation.py \
  tests/test_rf11_o2c_data_dictionary.py \
  tests/test_rf11_o2c_hypothesis_matrix.py \
  tests/test_rf11_o2c_taxonomy.py \
  tests/test_rf11_o2c_catalog_execution.py \
  tests/test_rf11_o2c_graph_integration.py
```

## Grafo multiagente

```bash
python3 -m pytest -q \
  tests/test_rf14_graph_routing.py \
  tests/test_rf14_graph_integration.py \
  tests/test_rf15c_multiagent_integration.py \
  tests/test_rf15c_end_to_end_contract.py
```

## Cloud/AWS

Los tests RF14c usan mocks/fakes y no ejecutan contra AWS real en CI:

```bash
python3 -m pytest -q \
  tests/test_rf14c07_env_config.py \
  tests/test_rf14c08_s3_io.py \
  tests/test_rf14c09_artifact_hash.py \
  tests/test_rf14c09_run_metadata.py \
  tests/test_rf14c10_state_store.py \
  tests/test_rf14c11_cloud_runner.py \
  tests/test_rf14c12_run_outputs.py \
  tests/test_rf14c23_lambda_trigger.py
```

La evidencia AWS real está documentada en:

- `docs/cloud/cloud_aws.md`
- `docs/cloud/rf14c_final_verification.md`
- `docs/cloud/evidences/`

## Suite completa

```bash
python3 -m pytest -q
```

La suite completa requiere todas las dependencias del proyecto instaladas. No requiere secretos para los tests que usan mocks/fakes. Los workflows con LLM real dependen de `OPENAI_API_KEY` y, opcionalmente, `LANGSMITH_API_KEY`.
