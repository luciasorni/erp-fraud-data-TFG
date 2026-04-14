# RF14c-05 — Estructura lógica S3

## Objetivo
Definir la estructura lógica del bucket S3 para soportar:
- inputs,
- artefactos,
- estado,
- resultados por run,
- ejecución multi-dominio (`p2p`, `o2c`, `both`)

La arquitectura utilizará **un único bucket S3** con prefijos lógicos.

## Decisión de diseño
Se adopta un solo bucket S3 para RF14c y la organización interna se hará mediante prefijos.

Motivo:
- simplifica naming,
- simplifica permisos IAM,
- simplifica operación,
- evita dispersar recursos innecesariamente.

## Estructura lógica acordada

```text
s3://tfg-fraud-dev-euw1-lucia01/
  inputs/
    datasets/
      p2p/
      o2c/
    docs/
      shared/
      p2p/
      o2c/
  artifacts/
    prompts/
      shared/
      p2p/
      o2c/
    catalogs/
      p2p/
      o2c/
    mappings/
      p2p/
      o2c/
  state/
    p2p/
    o2c/
    both/
  runs/
    <run_id>/
```

## Significado de cada prefijo

### `inputs/datasets/`
Contiene datasets de entrada por dominio:
- `inputs/datasets/p2p/`
- `inputs/datasets/o2c/`

### `inputs/docs/`
Contiene documentación base para KB o soporte del sistema:
- `inputs/docs/shared/`
- `inputs/docs/p2p/`
- `inputs/docs/o2c/`

### `artifacts/prompts/`
Contiene prompts versionados del sistema:
- `artifacts/prompts/shared/`
- `artifacts/prompts/p2p/`
- `artifacts/prompts/o2c/`

### `artifacts/catalogs/`
Contiene catálogos de tests por dominio:
- `artifacts/catalogs/p2p/`
- `artifacts/catalogs/o2c/`

### `artifacts/mappings/`
Contiene mappings y configuraciones específicas por dominio:
- `artifacts/mappings/p2p/`
- `artifacts/mappings/o2c/`

### `state/`
Contiene estado persistente del sistema por scope:
- `state/p2p/`
- `state/o2c/`
- `state/both/`

Aquí se almacenarán más adelante elementos como:
- `last_artifact_hash.json`

### `runs/<run_id>/`
Contiene los resultados de cada ejecución cloud.

La estructura interna del run se considera **estructura objetivo** para la fase cloud y debe servir de referencia para outputs técnicos y artefactos del grafo/agentes.

Estructura objetivo esperada:

```text
runs/<run_id>/
  run_metadata.json
  schema_summary.json
  report.json
  ranking.json
  graph/
    graph_state.json
    hypotheses.json
    selected_tests.json
    findings.json
    explanations.json
    explanations.md
    scores.json
    second_level_analysis.json
    second_level_analysis.md
```

Notas:
- no todos estos artefactos tienen por qué existir todavía en todas las fases del proyecto,
- pero esta es la estructura de referencia esperada para el despliegue cloud completo,
- los artefactos `second_level_analysis.*` corresponden a RF16/RF16b.

## Decisiones de separación por dominio

### Separación obligatoria por dominio
Se separan por dominio:
- datasets,
- catálogos,
- mappings,
- estado

### Separación flexible por dominio
Se permite separación por dominio en:
- docs,
- prompts

Motivo:
pueden existir recursos compartidos y otros específicos.

## Relación con `PROCESS_SCOPE`
La ejecución cloud se controlará con:

```text
PROCESS_SCOPE=p2p|o2c|both
```

Este parámetro determinará qué partes de `inputs/`, `artifacts/` y `state/` se consultan durante el run.

### Caso `PROCESS_SCOPE=both`
En cloud, `PROCESS_SCOPE=both` representa una ejecución única que procesa ambos dominios dentro del mismo `run_id`, manteniendo separación lógica interna por dominio cuando aplique.

## Convenciones
- usar solo minúsculas
- usar `/` como jerarquía lógica de prefijos
- no usar espacios
- no mezclar `P2P` y `p2p`
- no crear prefijos alternativos fuera de este esquema sin documentarlo

## Nota sobre `runs/<run_id>/`
Aunque `PROCESS_SCOPE=both`, se mantiene una única carpeta de run:
- `runs/<run_id>/`

y la separación interna por dominio se resolverá dentro del propio run en tareas posteriores.

## Criterio de done de RF14c-05
RF14c-05 se considera terminado cuando:
1. existe `docs/s3_layout.md`,
2. queda decidido que habrá un solo bucket,
3. queda definida la estructura lógica por prefijos,
4. queda definida la separación por dominio,
5. queda claro que `runs/<run_id>/` será el punto de salida de cada ejecución.

**Nota:** esta tarea define únicamente la estructura lógica del bucket. La creación real del bucket y de los prefijos se realizará en RF14c-06.
