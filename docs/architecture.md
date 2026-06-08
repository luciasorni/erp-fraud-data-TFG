# Arquitectura final del sistema

Este documento resume la arquitectura vigente del proyecto. La descripción histórica de fase 1 se conserva en `docs/legacy/architecture_phase1.md`.

## Objetivo

El sistema analiza datasets ERP controlados para detectar señales antifraude en procesos `P2P` y `O2C`. La arquitectura separa la preparación de datos, la ejecución determinista de pruebas, la capa multiagente, la persistencia de artefactos y la operación mediante API/UI.

## Componentes principales

| Componente | Ruta principal | Función |
|---|---|---|
| CLI / pipeline | `src/erp_fraud/cli/main.py` | Ejecuta ingesta, validación, tests, ranking, reporte y modo graph. |
| Ingesta | `src/erp_fraud/ingest/` | Lee ZIP ERP, carga datos tabulares y normaliza tipos. |
| Storage y artefactos | `src/erp_fraud/storage/` | DuckDB, metadata, schema summary, reportes, S3, state y comparación de runs. |
| Catálogo antifraude | `tests/catalog`, `tests/catalog_o2c`, `sql/tests`, `src/erp_fraud/catalog/` | Define y ejecuta pruebas antifraude SQL P2P/O2C. |
| Grafo multiagente | `src/erp_fraud/graph/` | Orquesta hipótesis, selección de tests, ejecución, explicación, scoring, persistencia y segundo nivel cuando aplica. |
| Agentes / guardrails / KB | `src/erp_fraud/agents/`, `config/agent_policies.yaml`, `config/query_templates.yaml`, `config/kb_*.yaml` | Control de herramientas, schema guard, KB local acotada y loop de reparación. |
| API | `app/api/` | Expone datasets, runs, resultados, reportes y drilldown sobre `/api/v1`. |
| UI | `app/ui/` | Interfaz Streamlit multipágina conectada a la API. |
| Cloud batch | `Dockerfile`, `docs/cloud/`, `.github/workflows/ecr-publish-main.yml`, `lambda/rf14c23/` | Ejecución AWS con S3, ECR, ECS Fargate, CloudWatch, Secrets Manager y triggers documentados. |
| EC2 defensa | `scripts/run_api_prod.sh`, `scripts/run_streamlit_prod.sh`, `deploy/*.service` | Despliegue público simple de API local + Streamlit pública. |

## Flujo lógico

1. El usuario registra o selecciona un dataset ERP.
2. El sistema prepara el dataset y genera contexto técnico (`schema_summary`, metadata y validación).
3. El catálogo antifraude define qué tests son ejecutables según familia de proceso y requisitos de datos.
4. El modo determinista ejecuta tests, ranking y reporte.
5. El modo graph añade hipótesis, selección de tests, findings, explicaciones, scoring y persistencia del estado del grafo.
6. Los resultados se conservan como artefactos por `run_id`.
7. La API y la UI consultan esos artefactos y ejecutan drilldown seguro.

## Modos de ejecución

| Modo | Descripción |
|---|---|
| `deterministic` | Pipeline base: ingesta, validación, tests, ranking y reporte. |
| `graph` | Pipeline base más grafo multiagente y artefactos `graph/*`. |
| `p2p` | Ejecuta la familia P2P. |
| `o2c` | Ejecuta la familia O2C con modelo/mapping canónico. |
| `both` | Alcance cloud/API para P2P+O2C. En API se resuelve como dos runs separados. No existe `process_family=both`. |

## Despliegues

### Local

El modo local se usa para desarrollo, tests y validación reproducible. Escribe artefactos en `run_results/<run_id>/`.

### AWS batch

La ejecución cloud batch se apoya en ECS Fargate y S3. La documentación consolidada está en `docs/cloud/cloud_aws.md`.

### EC2 pública

La vía de defensa publica Streamlit en `0.0.0.0:8501` y mantiene FastAPI en `127.0.0.1:8000`. La UI consume la API local y la API orquesta AWS para runs reales.

## Decisiones de diseño

- No se expone SQL libre al usuario.
- Las pruebas antifraude proceden de un catálogo versionado.
- El grafo multiagente opera sobre contexto, catálogo y artefactos, no sobre ejecución libre.
- Cada run deja artefactos revisables.
- O2C se implementa con modelo canónico y configuración separada.
- KB/RAG local y LangSmith son capacidades acotadas u opcionales, no requisitos para toda ejecución.

## Limitaciones

- El sistema no determina fraude real; prioriza señales revisables.
- La cobertura del catálogo no es universal.
- O2C está validado dentro del alcance del TFG.
- La API EC2 no sustituye el backend batch: para runs reales depende de AWS.
