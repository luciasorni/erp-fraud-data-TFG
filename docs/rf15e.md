# RF15e - Estado

## Alcance (inicio)

PoC de RAG/KB para indexar fuentes relevantes del proyecto y permitir búsqueda posterior.

## RF15e-01 completado

Se definió inventario de fuentes a indexar en:

- `config/kb_sources.yaml`

Fuentes contempladas:

- referencias ACFE en PDF (requeridas):
  - `docs/external/data_analysis_slides_for_pdf.pdf`
  - `docs/external/data_analytics_tests.pdf`
  - `docs/external/red_flags_final.pdf`
- `docs/*.md` del proyecto
- `data_dictionary.json` y `data_dictionary.md`
- catálogo de tests `tests/catalog/*.yaml`
- changelog de tests
- placeholders opcionales para `mappings/`, `taxonomy` y `test_cards`

Se añadió helper de resolución para preparar siguientes tareas:

- `src/erp_fraud/agents/kb_sources.py`
  - `load_kb_sources_config(...)`
  - `resolve_kb_sources(...)`

Objetivo técnico de esta fase:

- tener lista blanca explícita de fuentes KB,
- distinguir fuentes `required` vs `optional`,
- saber cuáles están disponibles antes de construir índice.

## RF15e-02 completado

Se implementó extracción de texto para:

- PDF (por página)
- Markdown / texto plano

Módulo:

- `src/erp_fraud/agents/kb_text_extractor.py`

Funciones principales:

- `extract_text_from_pdf(...)`
- `extract_text_from_markdown_or_text(...)`
- `extract_text_from_path(...)`
- `normalize_text(...)`
- `save_normalized_text_documents(...)`

Salida normalizada persistida:

- `normalized_documents.jsonl` (secciones + metadata + hash)
- `normalized_corpus.txt` (corpus agregado)

## RF15e-03 completado

Se definió estrategia de chunking y metadata de chunks.

Configuración:

- `config/kb_chunking.yaml`
  - `chunk_size`
  - `chunk_overlap`
  - `min_chunk_size`

Implementación:

- `src/erp_fraud/agents/kb_chunking.py`
  - `load_kb_chunking_config(...)`
  - `chunk_extracted_documents(...)`
  - `save_kb_chunks_jsonl(...)`

Metadata por chunk:

- `source_id`, `source_path`
- `section_id` (página/sección origen)
- `chunk_id`, `chunk_index`
- `text_hash`
- `chunk_start`, `chunk_end`
- `source_hash` (hash del texto de sección origen)

## RF15e-04 completado

Se inicializó soporte de ChromaDB persistente para KB.

Configuración:

- `config/kb_chroma.yaml`
  - `persist_directory` (default: `kb/chroma`)
  - `collection_prefix`
  - `default_doc_types`

Implementación:

- `src/erp_fraud/agents/kb_chroma.py`
  - `load_kb_chroma_config(...)`
  - `init_kb_chroma_client(...)`
  - `ensure_kb_collections(...)`
  - `infer_doc_types_from_chunks(...)`

Comportamiento:

- crea cliente Chroma persistente en ruta configurada,
- crea/asegura colecciones por tipo de documento (`pdf`, `md`, `txt`, ...),
- deja base lista para `build_index()` en tareas siguientes.

## RF15e-05 completado

Se implementó `build_index()` para recorrer fuentes, calcular hash, generar embeddings y hacer upsert en Chroma.

Implementación:

- `src/erp_fraud/agents/kb_index.py`
  - `build_kb_index(...)`
  - `build_kb_index_manifest_row(...)`

Flujo:

1. Carga fuentes (`kb_sources.yaml`) y valida requeridas.
2. Extrae texto normalizado por fichero.
3. Genera chunks según `kb_chunking.yaml`.
4. Inicializa Chroma (`kb_chroma.yaml`) y asegura colecciones por doc_type.
5. Hace `upsert` por chunk con:
   - `id = chunk_id`
   - `document = chunk.text`
   - `metadata` trazable (source, section, hashes)
   - `embedding` determinista local (hash-based, sin dependencia de servicio externo).
6. Guarda manifiesto de build (`kb/index_manifest.json`).

## RF15e-06 completado

Se implementó reconstrucción incremental basada en hash de fichero.

Implementación:

- `src/erp_fraud/agents/kb_index.py`
  - `build_kb_index(..., incremental_rebuild=True, index_state_path=...)`

Comportamiento:

- si `source_file_hash` no cambia respecto al estado previo -> se omite re-embed/upsert,
- si cambia -> se vuelve a extraer/chunkear/indexar solo ese fichero,
- se guarda estado en `kb/index_state.json` con hashes por ruta.

Evidencias en manifiesto de build:

- `sources_used` (reindexadas)
- `sources_skipped` (sin cambios)
- `incremental_rebuild`

## RF15e-07 completado

Se implementó `KBSearchTool(query, top_k, filters)` para consultar chunks en Chroma con score y metadata.

Implementación:

- `src/erp_fraud/agents/kb_search.py`
  - `KBSearchTool.search(query, top_k, filters)`

Comportamiento:

- valida `query` (mínimo 3 caracteres) y `top_k` (>0),
- genera embedding determinista local de la consulta,
- busca en las colecciones KB existentes,
- combina resultados y devuelve ranking global con:
  - `chunk_id`
  - `score` y `distance`
  - `metadata` (source_id/source_path/section/chunk hashes)
  - `collection`
- soporta `filters` por igualdad exacta sobre metadata.

Contrato de tool actualizado:

- `config/tools_registry.yaml` (`KBSearch.inputs.filters`).

## RF15e-08 completado

Se añadieron pruebas unitarias para cubrir los escenarios clave del índice y búsqueda KB.

Tests nuevos:

- `tests/test_rf15e_kb.py`

Cobertura incluida:

- índice vacío -> `build_kb_index` indexa contenido,
- rebuild sin cambios -> no reindexa (`sources_skipped`),
- rebuild con cambio en fichero -> reindexa solo lo modificado,
- búsqueda KB -> devuelve `hits` con `metadata` y `score`.

## RF15e-09 completado

Se integró la construcción de índice KB en el pipeline principal `erp-fraud run`.

Implementación:

- `src/erp_fraud/cli/main.py`
  - integración de `build_kb_index(...)` en `_run_pipeline(...)` con `incremental_rebuild=True`,
  - nuevos artefactos de run:
    - `kb_index_manifest.json`
    - `kb_index_state.json`
  - nuevos parámetros de run:
    - `--kb-index-enabled` / `--no-kb-index`
    - `--kb-sources-config`
    - `--kb-chunking-config`
    - `--kb-chroma-config`

Comportamiento:

- por defecto no reconstruye el índice KB durante el run,
- solo reconstruye KB si se solicita explícitamente con `--kb-index-enabled`,
- si falla el indexado KB, se registra warning y el pipeline continúa (no bloqueante),
- `report.json` y metadatos del run incluyen estado/config de KB cuando aplica.

## RF15e-10 completado

Se documentó la KB en una guía dedicada:

- `docs/rag_kb.md`

Incluye:

- fuentes indexadas y configuración,
- rebuild incremental y flags CLI,
- artefactos generados por run,
- ejemplo de uso de `KBSearchTool`,
- procedimiento para añadir nuevas fuentes,
- troubleshooting básico.

## RF15e-11 completado

Se ampliaron/ajustaron tests unitarios de RF15e.

Tests:

- `tests/test_rf15e_kb.py`
  - build inicial, rebuild sin cambios, rebuild con cambio,
  - `KBSearchTool` devolviendo `metadata` y `score`.
- `tests/test_rf15e_cli_kb_integration.py`
  - defaults de settings KB en CLI,
  - rutas de artefactos KB por run,
  - flag `--no-kb-index` sobrescribiendo default.

## RF15e-12 completado

Documentación actualizada para operación/verificación de KB:

- `docs/rag_kb.md` (runbook RF15e),
- `docs/how_to_run.md` (comandos de run con/sin KB y artefactos KB),
- `README.md` (sección resumen RF15e y módulos).

## RF15e-13 completado

Verificación ejecutada y evidencias guardadas en:

- `run_results/rf15e-13-check/pytest_rf15e.log`
- `run_results/rf15e-13-check/kb_index_manifest.json`
- `run_results/rf15e-13-check/kb_index_state.json`
- `run_results/rf15e-13-check/kb_search_sample.json`
- `run_results/rf15e-13-check/verification_summary.json`

Resultado de verificación:

- `pytest` RF15e: **5 passed**
- build KB: índice generado correctamente
- search KB: devuelve hits con metadata

Nota:

- En este entorno no se integra LangSmith todavía, por eso RF15e-13 se cierra con artefactos locales y logs del run.
