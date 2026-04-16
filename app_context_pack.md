# App Context Pack

## Árbol relevante

```text
app/
  api/
    main.py
    routers/
      datasets.py
      drilldown.py
      health.py
      runs.py
    schemas/
      datasets.py
      drilldown.py
      operations.py
      results.py
      runs.py
    services/
      aws_service.py
      datasets_service.py
      drilldown_service.py
      operations_service.py
      results_service.py
      runs_service.py
  ui/
    Home.py
    pages/
      1_Nuevo_analisis.py
      2_Ejecuciones.py
      3_Resultados.py
      4_Detalle_hallazgo.py
      5_Como_funciona.py
    components/
      dataset_summary.py
      drilldown_table.py
      explanations_panel.py
      findings_detail.py
      findings_list.py
      header.py
      recommendations_panel.py
      run_metrics.py
      run_table.py
      status_badge.py
    services/
      api_client.py
    utils/
      constants.py
      formatters.py
      mappers.py
      session_state.py

src/erp_fraud/
  cli/main.py
  config/env.py
  graph/
    llm_runtime.py
    langsmith_runs.py
    observability.py
    nodes/
      common.py
      planning.py
```

## Archivos importantes y qué hace cada uno

### `app/api/main.py`
- Crea la aplicación FastAPI y monta los routers bajo `/api/v1`.
- Ahora importa `src.erp_fraud.config.env` al arrancar para cargar `.env` antes de usar servicios que dependen de `os.environ`.
- Es el punto de entrada correcto cuando levantas `uvicorn app.api.main:app`.

### `app/api/services/aws_service.py`
- Centraliza sesión `boto3`, acceso a S3, lanzamiento de tasks ECS y lectura de artefactos en cloud.
- Construye el `containerOverrides` para runs graph en Fargate.
- Aquí se decide qué variables de entorno del proceso API se reenvían al contenedor ECS.
- En esta ronda se añadió carga de `.env` y forwarding de `OPENAI_API_KEY` / `LANGSMITH_*`.

### `app/api/services/runs_service.py`
- Orquesta `POST /runs`, detalle de runs y composición de estado a partir de `api_request.json`, `run_metadata.json`, `graph_state.json` y ECS.
- `scope=both` se resuelve como dos runs reales (`p2p` y `o2c`).
- Es la capa que usa la API para lanzar runs desde la UI.

### `app/api/services/results_service.py`
- Lee artefactos graph desde S3 y los normaliza para la UI.
- Construye payloads legibles para `hypotheses`, `selected_tests`, `findings`, `scores`, `explanations`, `comparison_insights` y `recommendations`.
- Aquí también se separa narrativa útil frente a errores técnicos de ejecución.

### `app/api/services/drilldown_service.py`
- Ejecuta drilldown seguro sin SQL libre.
- Valida la acción permitida, recibe `test_id + keys`, consulta el backend de evidencia y devuelve tabla lista para UI.

### `app/api/services/operations_service.py`
- Implementa jobs cortos con polling para operaciones largas de UI.
- Se usa para `upload-jobs` y `drilldown-jobs`.
- Evita dejar a Streamlit bloqueado en una petición síncrona larga.

### `app/ui/services/api_client.py`
- Cliente HTTP centralizado de Streamlit hacia FastAPI.
- Contiene todas las llamadas usadas por las páginas: datasets, runs, graph, report, drilldown y jobs.
- Gestiona timeouts y traduce errores de red/API a mensajes de UI.

### `app/ui/utils/session_state.py`
- Define e inicializa el estado compartido entre páginas Streamlit.
- Guarda dataset seleccionado, run actual, hallazgo actual, filtros, wizard de `Nuevo análisis` y último resultado de drilldown.
- Incluye el reset del flujo de `Nuevo análisis`.

### `app/ui/utils/mappers.py`
- Adapta payloads de la API a estructuras legibles de UI.
- Extrae score, interpretaciones, comparativas, explanations por test y filas de findings.
- También construye el contenido que usa `Detalle hallazgo` para listar todos los hallazgos de un test.

### `app/ui/pages/1_Nuevo_analisis.py`
- Flujo guiado en 3 pasos: dataset, configuración y confirmación.
- Usa jobs de upload con polling y feedback visual.
- Al entrar desde fuera del flujo se reinicia al paso 1.

### `app/ui/pages/2_Ejecuciones.py`
- Lista runs, destaca la ejecución más reciente y hace refresh periódico cuando un run sigue activo.
- Muestra estado, timestamps, scope y acceso a resultados.

### `app/ui/pages/3_Resultados.py`
- Es la vista principal de un run: cabecera, KPIs, score, tabs y trazabilidad del planner.
- Consume `/runs/{id}`, `/runs/{id}/graph` y `/runs/{id}/report`.
- Aquí se renderiza el bloque “Trazabilidad del planner”.

### `app/ui/pages/4_Detalle_hallazgo.py`
- Vista autónoma de detalle: permite elegir run, elegir finding/test y elegir el hallazgo concreto dentro de ese finding.
- Ya no depende exclusivamente de haber navegado desde Resultados.
- El drilldown se ejecuta sobre las `keys` del hallazgo seleccionado en esa misma página.

### `app/ui/pages/5_Como_funciona.py`
- Página explicativa para demo/producto.
- Resume P2P, O2C, hipótesis, tests, findings, scoring, explanations y second-level explainer.

### `src/erp_fraud/config/env.py`
- Capa común de lectura/normalización de variables de entorno.
- Ahora carga `.env` automáticamente cuando el proyecto arranca localmente.
- Expone helpers para `RUN_MODE`, `PROCESS_SCOPE`, defaults cloud y LangSmith.

### `src/erp_fraud/graph/llm_runtime.py`
- Wrapper de llamadas reales a OpenAI.
- Decide `ERROR_NO_API_KEY`, `ERROR_OPENAI_NOT_INSTALLED`, `ERROR_OPENAI_CALL:*` o `OK`.
- Devuelve `status`, `fallback_used`, tokens, coste estimado y modelo usado.

### `src/erp_fraud/graph/nodes/planning.py`
- Implementa `hypothesis_planner` y `test_planner`.
- Decide LLM real vs heurística allowlist según `llm_mode`, provider, modelo y resultado de la llamada.
- En esta ronda se ajustó la trazabilidad para que la salida LLM se marque como `planner_llm`.

### `src/erp_fraud/graph/observability.py`
- Reúne snapshot de observabilidad y configuración de tracing.
- Lee si LangSmith está realmente configurado (`api key`, tracing y project).

### `src/erp_fraud/graph/langsmith_runs.py`
- Publica trazas sintéticas de nodos a LangSmith al terminar el grafo.
- Devuelve `status`, `reason`, `root_run_id` y `trace_link`.
- Es la pieza que hoy falla en cloud con `403 Forbidden`.

### `src/erp_fraud/cli/main.py`
- Runner principal del proyecto en local y cloud.
- En `RUN_MODE=cloud` descarga inputs, materializa workspace y ejecuta el pipeline local dentro del contenedor.
- Es el proceso que corre realmente dentro de ECS/Fargate.

## Flujo completo de la aplicación

### 1. Nuevo análisis
1. La UI carga datasets disponibles con `GET /api/v1/datasets`.
2. Si subes ZIP, Streamlit llama a `POST /api/v1/datasets/upload-jobs`.
3. La UI hace polling de `GET /api/v1/datasets/upload-jobs/{job_id}` hasta `SUCCEEDED`.
4. En la confirmación final, `POST /api/v1/runs` crea el run cloud.
5. Se guarda `selected_run_id` o `selected_run_ids` en `session_state`.

### 2. Ejecuciones
1. La UI consulta `GET /api/v1/runs`.
2. Si hay runs activos, refresca periódicamente.
3. El usuario puede abrir uno y pasar a Resultados o Detalle.

### 3. Resultados
1. Carga `GET /api/v1/runs/{run_id}` para estado y metadata.
2. Carga `GET /api/v1/runs/{run_id}/graph` para artefactos legibles.
3. Carga `GET /api/v1/runs/{run_id}/report` para report auxiliar.
4. Renderiza score, hypotheses, selected tests, findings, explanations, comparativas y recommendations.
5. La trazabilidad del planner se pinta desde `detail.metadata.graph_run_metadata`.

### 4. Detalle hallazgo
1. La propia página carga runs con `GET /api/v1/runs`.
2. El usuario elige un run.
3. La página carga `GET /api/v1/runs/{run_id}/graph`.
4. Construye la lista de findings/test y, dentro de cada finding, el selector de hallazgos concretos.
5. El usuario elige el hallazgo y se renderizan explicación, evidencia, comparativas, recomendaciones y drilldown.

### 5. Drilldown
1. Streamlit llama a `POST /api/v1/runs/{run_id}/drilldown-jobs`.
2. El backend crea un job asíncrono y ejecuta el drilldown seguro.
3. La UI hace polling con `GET /api/v1/runs/{run_id}/drilldown-jobs/{job_id}`.
4. El resultado se muestra en tabla con `drilldown_table.py`.

## Origen de datos por pantalla

### Home
- No depende de artefactos complejos.
- Puede usar `GET /runs` para actividad reciente y navegación rápida.

### Nuevo análisis
- `GET /datasets`
- `GET /datasets/{dataset_id}`
- `POST /datasets/upload-jobs`
- `GET /datasets/upload-jobs/{job_id}`
- `POST /runs`

### Ejecuciones
- `GET /runs`

### Resultados
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/graph`
- `GET /runs/{run_id}/report`

### Detalle hallazgo
- `GET /runs`
- `GET /runs/{run_id}/graph`
- `POST /runs/{run_id}/drilldown-jobs`
- `GET /runs/{run_id}/drilldown-jobs/{job_id}`

## Session state usado por la UI

- `selected_dataset_id`
- `selected_scope`
- `analysis_step`
- `llm_mode`
- `kb_index_enabled`
- `selected_run_id`
- `selected_run_ids`
- `selected_finding_id`
- `selected_finding`
- `selected_finding_row_key`
- `selected_graph_payload`
- `selected_run_detail`
- `last_run_response`
- `runs_filters`
- `drilldown_result`
- `_active_page`

## Endpoints FastAPI por página

### `Home.py`
- uso ligero de runs si se quiere actividad reciente

### `1_Nuevo_analisis.py`
- `GET /api/v1/datasets`
- `GET /api/v1/datasets/{dataset_id}`
- `POST /api/v1/datasets/upload-jobs`
- `GET /api/v1/datasets/upload-jobs/{job_id}`
- `POST /api/v1/runs`

### `2_Ejecuciones.py`
- `GET /api/v1/runs`

### `3_Resultados.py`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/graph`
- `GET /api/v1/runs/{run_id}/report`

### `4_Detalle_hallazgo.py`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}/graph`
- `POST /api/v1/runs/{run_id}/drilldown-jobs`
- `GET /api/v1/runs/{run_id}/drilldown-jobs/{job_id}`

## Artefactos que lee cada vista

### Resultados
- `graph/graph_state.json`
  - `hypotheses`
  - `selected_tests`
  - `findings`
  - `scores`
  - `explanations`
  - `second_level_analysis`
  - `run_metadata`
- `report.json`
- `run_metadata.json`
- `api_request.json`

### Detalle hallazgo
- `graph/graph_state.json`
  - findings enriquecidos
  - explanations
  - comparison_insights
  - recommendations
  - executive_summary
- resultado de `drilldown`

## Dónde se decide LLM vs fallback

### Planner / explainers / scoring
- `src/erp_fraud/graph/llm_runtime.py`
  - comprueba credenciales, SDK y llamada OpenAI real.
- `src/erp_fraud/graph/nodes/planning.py`
  - si la llamada real falla, cae a `planner_allowlist_heuristic` o fallback del planner.
- `src/erp_fraud/graph/nodes/...`
  - expert explainer, second-level explainer y scoring usan el mismo runtime/fallback pattern.

### Cloud run
- `app/api/services/aws_service.py`
  - decide qué credenciales del proceso API se pasan al contenedor ECS.

## Dónde se renderiza la trazabilidad del planner

- `app/ui/pages/3_Resultados.py`
  - función `_render_planner_trace(...)`
  - usa `detail.metadata.graph_run_metadata`
  - campos clave:
    - `hypothesis_llm_call_status`
    - `test_planner_llm_call_status`
    - `llm_runtime_by_node`
    - `item.status` como “Salida mostrada”

## Dónde se construye el selector de hallazgos y el drilldown

### Selector de hallazgos
- `app/ui/pages/4_Detalle_hallazgo.py`
  - `findings_available = findings_table_rows(graph["findings"])`
  - selector de finding/test
  - selector de hallazgo concreto dentro de `finding["rows"]`

### Drilldown
- `app/ui/pages/4_Detalle_hallazgo.py`
  - toma `evidence_keys` del hallazgo seleccionado
  - llama a `client.start_drilldown_job(...)`
  - hace polling con `client.get_drilldown_job(...)`
- `app/api/services/drilldown_service.py`
  - ejecuta el drilldown seguro

## Estado real de LLM / fallback / tracing en esta ronda

- Local:
  - `OpenAI` real funciona.
  - `planner_llm` real funciona.
  - `publish_langsmith_node_runs(...)` funciona.
  - la misma imagen Docker funciona localmente con OpenAI y LangSmith.

- Cloud ECS:
  - el task recibe `OPENAI_API_KEY` y `LANGSMITH_*`.
  - aun así, `graph_state.json` del run real muestra:
    - `hypothesis_llm_call_status = ERROR_OPENAI_CALL:AuthenticationError`
    - `test_planner_llm_call_status = ERROR_OPENAI_CALL:AuthenticationError`
    - `langsmith_runs.status = ERROR`
    - `langsmith_runs.reason = 403 Forbidden`
  - eso indica un bloqueo específico del entorno ECS, no del runtime local ni del código de UI.

## Archivos tocados en esta ronda

- `app/api/main.py`
- `app/api/services/aws_service.py`
- `app/ui/utils/session_state.py`
- `app/ui/pages/1_Nuevo_analisis.py`
- `app/ui/pages/4_Detalle_hallazgo.py`
- `src/erp_fraud/config/env.py`
- `src/erp_fraud/graph/nodes/planning.py`
