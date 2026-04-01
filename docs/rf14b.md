# RF14b — LangSmith (Trazabilidad y Evaluación)

Este documento explica RF14b en formato práctico.

## Qué es LangSmith (en este proyecto)

LangSmith nos sirve para 3 cosas:

1. Ver la traza del grafo por nodos/agentes (qué entró, qué salió, dónde falló).
2. Comparar ejecuciones/modelos con evidencia reproducible.
3. Medir evaluaciones automáticas (si una salida cumple esquema y guardrails).

No sustituye al pipeline: añade observabilidad y evaluación encima de lo que ya ejecuta el proyecto.

## RF14b-01 — Setup mínimo

### 1) Crear proyecto en LangSmith (UI)

En `smith.langchain.com`:

1. Crea un proyecto con nombre recomendado: `erp-fraud-tfg`.
2. Etiquetas recomendadas: `rf14b`, `langgraph`, `p2p`, `tfg`.

### 2) Configurar variables de entorno

Variables mínimas:

- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`

Opcionales:

- `LANGSMITH_TRACING=true`
- `LANGCHAIN_TRACING_V2=true`
- `LANGSMITH_ENDPOINT` (si usas endpoint no estándar)

Ejemplo local:

```bash
export LANGSMITH_API_KEY="tu_api_key"
export LANGSMITH_PROJECT="erp-fraud-tfg"
export LANGSMITH_TRACING="true"
export LANGCHAIN_TRACING_V2="true"
```

### 3) Validar que el setup está correcto

```bash
python3 scripts/validate_required_env.py --profile langsmith
```

Si falla, falta alguna variable obligatoria.

## Estado actual del código (hoy)

- El proyecto ya captura snapshot de configuración LangSmith en nodos de grafo.
- Si LangSmith no está configurado, el flujo **no se bloquea** (modo opcional/no bloqueante).
- RF14b continúa con instrumentación de trazas por nodo y datasets/experimentos de evaluación.

## Qué haremos después de RF14b-01

- `RF14b-02`: instrumentar trazas por nodo/agente en LangGraph.
- `RF14b-05...08`: evaluaciones automáticas + dataset de evaluación + comparativa de modelos.

## RF14b-02 (estado implementado en código)

Ya está instrumentado en el runner del grafo:

- `run_metadata["node_trace_events"]` guarda eventos `start/end` por nodo con:
  - `node_id`, `stage`, `attempt`, `status`, `duration_ms`
  - `input_summary` / `output_summary` (resumen de estado, no payload masivo)
  - `error` cuando aplica
- `run_metadata["langsmith"]` guarda snapshot de configuración detectada:
  - `tracing_enabled`, `api_key_present`, `project`, `endpoint`, `configured`

Objetivo práctico:
- Aunque todavía no hagamos evaluación de experimentos en LangSmith, ya tienes trazabilidad
  uniforme por nodo para depurar y para mapear 1:1 con trazas externas en los siguientes pasos.
