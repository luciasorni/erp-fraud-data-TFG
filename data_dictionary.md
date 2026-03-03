# Data Dictionary (P2P, Fase 1)

Formato humano del diccionario de datos usado por los tests de fraude.

## Alcance

- Proceso: `P2P`
- Fuente: `ERP Fraud Data / joint_datasets`
- Estado: plantilla inicial (el contenido se rellenará en tareas posteriores)

## Formato de entrada (por campo)

Cada entrada del diccionario debe incluir:

- `table`: nombre de tabla en DuckDB
- `column`: nombre de columna
- `type`: tipo de dato (preferentemente el de `schema_summary.json`)
- `description`: descripción mínima del campo
- `examples`: ejemplos de valores (lista corta)
- `used_in_tests`: lista de `test_id` que usan el campo

## Convención de secciones (Markdown)

Estructura recomendada del documento cuando se rellene:

- una sección por tabla (`## Tabla: <table>`)
- dentro, una subsección por campo (`### <table>.<column>`)

## Plantilla de documento (por tabla)

```md
## Tabla: <table>

Descripcion breve de la tabla y su rol en el proceso (opcional, 1-2 lineas).

### `<table>.<column_1>`

- `table`: `<table>`
- `column`: `<column_1>`
- `type`: `<type>`
- `description`: `<descripcion>`
- `examples`: `["<ejemplo_1>", "<ejemplo_2>"]`
- `used_in_tests`: `[]`

### `<table>.<column_2>`

- `table`: `<table>`
- `column`: `<column_2>`
- `type`: `<type>`
- `description`: `<descripcion>`
- `examples`: `[]`
- `used_in_tests`: `[]`
```

## Plantilla de entrada (campo)

### `<table>.<column>`

- `table`: `<table>`
- `column`: `<column>`
- `type`: `<type>`
- `description`: `<descripcion>`
- `examples`: `["<ejemplo_1>", "<ejemplo_2>"]`
- `used_in_tests`: `[]`

## Ejemplo de entrada completa (referencia)

### `fraud_1.Belegnummer`

- `table`: `fraud_1`
- `column`: `Belegnummer`
- `type`: `VARCHAR`
- `description`: Identificador de documento/numero de asiento en el dataset conjunto.
- `examples`: `["100000000"]`
- `used_in_tests`: `[]`

## Secciones previstas (P2P / joint_datasets)

Estas secciones se rellenarán progresivamente a partir del `schema_summary.json` y de los tests:

- `## Tabla: column_information`
- `## Tabla: fraud_1`
- `## Tabla: fraud_1_expls`
- `## Tabla: fraud_2`
- `## Tabla: fraud_2_expls`
- `## Tabla: fraud_3`
- `## Tabla: fraud_3_expls`
- `## Tabla: normal_1`
- `## Tabla: normal_2`
