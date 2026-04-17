# Gobernanza del proyecto

## 1. Metodología de trabajo

El proyecto se ha desarrollado con enfoque ágil e iterativo, combinando:

- backlog funcional por requisitos (`RFxx`, `AGxx`);
- iteraciones incrementales sobre código, tests y documentación;
- validación continua mediante artefactos reproducibles y evidencias por `run_id`.

La planificación operativa se mantiene en:

- `project/backlog_tasks.txt`
- `project/requisitos_backlog.xlsx`

El fichero Excel se usa como equivalente operativo del backlog/tareas para seguimiento y priorización.

## 2. Definition of Ready (DoR)

Una tarea o requisito se considera listo para entrar en desarrollo si:

- tiene objetivo funcional claro;
- existe criterio de validación comprensible;
- está identificado el impacto sobre código, tests y documentación;
- el cambio no contradice el alcance definido en `docs/scope.md`;
- se puede verificar con evidencia ejecutable o documentable.

## 3. Definition of Done (DoD)

Una tarea o requisito se considera hecho si, de forma proporcionada a su tamaño:

- el cambio está implementado en código;
- existen tests o validación equivalente cuando aplica;
- la documentación visible al usuario o al evaluador está actualizada;
- los artefactos/resultados son coherentes con el comportamiento esperado;
- no rompe contratos previos relevantes del sistema.

## 4. Gestión de cambios del backlog

El backlog no se trata como una lista rígida e inmutable. Se aplica esta política:

- si un requisito cambia de forma pero ya está cubierto funcionalmente, se documenta la equivalencia;
- si una implementación resuelve varias tareas de backlog a la vez, se consolida la evidencia en documentación;
- si aparece un problema real durante validación, el backlog se ajusta para priorizar el fix sobre mejoras cosméticas;
- el cierre final del requisito se basa en evidencia técnica real, no solo en el nombre exacto del artefacto.

## 5. Evidencia aceptada

Para cerrar un requisito se acepta como evidencia una o varias de estas piezas:

- tests automatizados;
- artefactos de `run_results/<run_id>/`;
- documentación técnica en `docs/`;
- verificación cloud real;
- enlaces/trazas de LangSmith cuando aplica;
- validación manual reproducible cuando no existe mejor alternativa automatizable.

## 6. Ritmo de trabajo aplicado

El patrón real seguido en esta fase ha sido:

1. identificar requisito o bug;
2. diagnosticar causa raíz;
3. aplicar cambio mínimo coherente;
4. validar con tests y/o run real;
5. consolidar documentación y evidencia.

## 7. Cierre de alcance

La gobernanza del proyecto se apoya en:

- [scope.md](./scope.md)
- [hypothesis_matrix.md](./hypothesis_matrix.md)
- `project/backlog_tasks.txt`
- `project/requisitos_backlog.xlsx`

Con estos artefactos, el backlog queda trazado a implementación, validación y documentación final.
