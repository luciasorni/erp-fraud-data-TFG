# RAG / KB Local (RF15e)

## Objetivo

Mantener una base de conocimiento local en ChromaDB para apoyar planificación/explicación con contexto trazable del proyecto.

## Fuentes indexadas

Configuradas en `config/kb_sources.yaml`:

- PDFs ACFE (`docs/external/*.pdf`)
- documentación del proyecto (`docs/*.md`)
- diccionario de datos (`data_dictionary.json`, `data_dictionary.md`)
- catálogo de tests (`tests/catalog/*.yaml`)

Cada fuente se marca como `required` u `optional`.

## Configuración técnica

- Fuentes: `config/kb_sources.yaml`
- Chunking: `config/kb_chunking.yaml`
- Chroma: `config/kb_chroma.yaml`

Parámetros relevantes:

- `chunk_size`, `chunk_overlap`, `min_chunk_size`
- `persist_directory` (default `kb/chroma`)
- `collection_prefix` y `default_doc_types`

## Build / Rebuild del índice

Se ejecuta en el pipeline `run` (incremental por hash de fichero):

```bash
/opt/anaconda3/bin/python -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --kb-index-enabled
```

Desactivar indexado KB:

```bash
/opt/anaconda3/bin/python -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --no-kb-index
```

Sobrescribir configs KB:

```bash
/opt/anaconda3/bin/python -m src.erp_fraud.cli.main run \
  --input-zip erp_fraud_data.zip \
  --kb-sources-config config/kb_sources.yaml \
  --kb-chunking-config config/kb_chunking.yaml \
  --kb-chroma-config config/kb_chroma.yaml
```

## Artefactos generados

En `run_results/<run_id>/`:

- `kb_index_manifest.json`
- `kb_index_state.json`

Campos útiles del manifiesto:

- `sources_used`
- `sources_skipped`
- `chunks_indexed`
- `collections`

## Búsqueda KB

Tool implementada:

- `src/erp_fraud/agents/kb_search.py`
  - `KBSearchTool.search(query, top_k, filters)`

Ejemplo (uso desde código):

```python
from src.erp_fraud.agents import KBSearchTool

tool = KBSearchTool(base_dir=".")
result = tool.search(
    query="duplicate invoice vendor",
    top_k=5,
    filters={"source_id": "acfe_analytics_tests_pdf"},
)
```

Salida:

- `hits[]` con `chunk_id`, `score`, `distance`, `metadata`, `collection`

## Cómo añadir nuevas fuentes

1. Añadir entrada en `config/kb_sources.yaml`.
2. Indicar `glob` o ruta específica.
3. Marcar `required: true/false`.
4. Ejecutar `run` para rebuild incremental.
5. Verificar en `kb_index_manifest.json` que aparece en `sources_used` o `sources_skipped`.

## Troubleshooting

- `No module named chromadb`: instalar dependencias del `requirements.txt`.
- `No module named pypdf`: instalar dependencias del `requirements.txt`.
- fuente requerida no encontrada: revisar `glob`/ruta en `config/kb_sources.yaml`.
- índice no se actualiza: comprobar `kb_index_state.json` y que el hash del fichero cambió.
