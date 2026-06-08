# ERP Fraud Analysis Workbench

Sistema de TFG para análisis antifraude sobre datos ERP en procesos `P2P`
(procure-to-pay) y `O2C` (order-to-cash).

El proyecto implementa un pipeline reproducible que ingiere datasets ERP, ejecuta
pruebas antifraude, genera hallazgos y persiste artefactos por ejecución. Encima
del pipeline hay una API `FastAPI`, una interfaz `Streamlit` y una vía de
despliegue público en EC2 para revisión externa.

## Estado actual y alcance real

Implementado en el repositorio:

- Catálogo antifraude P2P y O2C con pruebas SQL versionadas.
- Pipeline determinista de ingesta, validación, ejecución de tests, ranking y
  reporte.
- Modo `graph` con hipótesis, selección de tests, hallazgos, scoring y
  explicaciones cuando aplica.
- Artefactos trazables por `run_id` en `run_results/<run_id>/` o S3.
- API `FastAPI` para datasets, runs, resultados, grafo, reporte y drilldown.
- UI `Streamlit` conectada a la API.
- Despliegue público de defensa en EC2.
- Arquitectura cloud batch documentada sobre S3, ECR, ECS Fargate, CloudWatch,
  Secrets Manager, IAM y automatización AWS.

Limitaciones importantes:

- El sistema prioriza análisis y priorización de señales; no determina por sí
  solo que exista fraude real.
- No expone SQL libre al usuario.
- La KB/RAG local es una extensión acotada y configurable, no una base de
  conocimiento corporativa completa.
- LangSmith forma parte de la observabilidad/validación del flujo multiagente
  cuando está configurado, pero no todos los runs tienen traza externa
  consolidada.
- La demo pública depende de que la instancia EC2 esté encendida.

## Demo pública

Demo temporal para revisión y defensa:

```text
http://100.57.8.239:8501
```

En esta vía de despliegue, Streamlit escucha en `0.0.0.0:8501` y consume una API
FastAPI local en la misma instancia:

```text
ERP_FRAUD_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

El puerto `8000` de FastAPI no se expone públicamente.

## Funcionalidades principales

- Carga y registro de datasets.
- Lanzamiento de análisis P2P u O2C.
- Consulta de runs y estado de ejecución.
- Visualización de ranking, hallazgos, evidencias y reporte.
- Drilldown controlado sobre hallazgos.
- Comparación de ejecuciones cuando hay artefactos compatibles.
- Persistencia de artefactos técnicos para auditoría y trazabilidad.

## Componentes principales

| Componente | Ruta principal | Función |
|---|---|---|
| Pipeline | `src/erp_fraud/` | Ingesta, validación, catálogo, ejecución, reporting y grafo |
| Catálogo P2P | `tests/catalog/` | Especificaciones de pruebas P2P |
| Catálogo O2C | `tests/catalog_o2c/` | Especificaciones de pruebas O2C |
| SQL de pruebas | `sql/tests/` | Consultas ejecutables del catálogo |
| API | `app/api/` | Servicio HTTP `FastAPI` |
| UI | `app/ui/` | Interfaz `Streamlit` |
| Configuración | `config/` | Pesos, modelos, O2C, KB, políticas y query templates |
| Despliegue | `scripts/`, `deploy/`, `docs/deploy_*.md` | Scripts y servicios EC2 |
| Tests | `tests/` | Suite `pytest` |

## Quick start local

Instalar dependencias:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Comprobar el CLI:

```bash
python3 -m src.erp_fraud.cli.main run --help
```

Ejecutar un run determinista local:

```bash
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --run-id demo-local
```

Ejecutar un run `graph` con stubs:

```bash
python3 -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --run-id demo-graph \
  --pipeline-mode graph \
  --llm-mode stub
```

## API y UI en local

Arrancar FastAPI:

```bash
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/api/v1/health
```

Arrancar Streamlit:

```bash
ERP_FRAUD_API_BASE_URL=http://127.0.0.1:8000/api/v1 \
streamlit run app/ui/Home.py
```

Entrypoints reales:

- API: `app.api.main:app`
- UI: `app/ui/Home.py`

## Despliegue

### EC2 pública para defensa

La vía recomendada para revisión externa despliega API y UI en la misma EC2:

- FastAPI en `127.0.0.1:8000`.
- Streamlit en `0.0.0.0:8501`.
- Security Group con `8501` abierto para navegador.
- Servicios `systemd` definidos en `deploy/`.

Documentación:

- `docs/deploy_api_ec2.md`
- `docs/deploy_streamlit_ec2.md`
- `docs/deployment.md`

### AWS batch

La arquitectura batch cloud está documentada en `docs/cloud/cloud_aws.md`.
Incluye S3, ECR, ECS Fargate, CloudWatch Logs, Secrets Manager e IAM. Esta vía
no sustituye la demo pública EC2; se mantiene como despliegue batch del pipeline.

## Configuración y secretos

Plantillas relevantes:

- `.env.example`: configuración local/general.
- `.env.api.ec2.example`: variables para la API en EC2.
- `.env.streamlit.ec2.example`: variables para Streamlit en EC2.

Los secretos reales no deben versionarse. En despliegue cloud se delegan en AWS
Secrets Manager cuando aplica. La UI no necesita claves LLM; consume la API
mediante `ERP_FRAUD_API_BASE_URL`.

## Testing y validación

Suite rápida de API/UI:

```bash
python3 -m pytest -q \
  tests/test_rf20_api.py \
  tests/test_rf20_services.py \
  tests/test_rf20_ui_api_client.py \
  tests/test_rf20_ui_utils.py
```

Suite base de pipeline:

```bash
python3 -m pytest -q \
  tests/test_rf01_ingest_storage.py \
  tests/test_rf02_data_dictionary.py \
  tests/test_rf02b_data_validation.py \
  tests/test_rf03_catalog.py \
  tests/test_rf04_runner.py \
  tests/test_rf05_result_schema_and_writer.py \
  tests/test_rf06_drilldown.py \
  tests/test_rf06_drilldown_components.py \
  tests/test_rf07_ranking.py \
  tests/test_rf08_reporting.py
```

Registro ampliado de pruebas y evidencias: `docs/testing.md`.

## Documentación adicional

- `docs/architecture.md`: arquitectura lógica del sistema.
- `docs/data.md`: datasets, familias de proceso y modelo de datos.
- `docs/catalog.md`: catálogo antifraude implementado.
- `docs/artifacts.md`: contrato de artefactos por run.
- `docs/deployment.md`: despliegues disponibles.
- `docs/cloud/cloud_aws.md`: arquitectura cloud batch.
- `docs/o2c/README.md`: documentación específica O2C.
- `docs/rag_kb.md`: alcance de la KB/RAG local.
- `docs/project_governance.md`: criterios de gobierno del proyecto.

## Estructura resumida del repositorio

```text
src/erp_fraud/       pipeline, catálogo, storage, graph y agentes
app/api/             API FastAPI
app/ui/              UI Streamlit
tests/               tests pytest y catálogos de pruebas
sql/tests/           SQL antifraude
config/              configuración funcional y técnica
scripts/             scripts de ejecución, verificación y despliegue
deploy/              servicios systemd
docs/                documentación técnica y memoria
run_results/         artefactos locales de ejecución
```
