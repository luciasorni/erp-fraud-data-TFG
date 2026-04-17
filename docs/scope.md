# Alcance del TFG

## 1. Frase evaluable del producto final

El TFG entrega un sistema reproducible para analizar datasets ERP en procesos `P2P` y `O2C`, ejecutar tests antifraude seleccionados a partir de hipótesis, generar explicaciones y scoring trazables, y operarlo desde cloud/API/UI sin exponer SQL libre ni depender de intervención manual.

## 2. Objetivos

- Cargar datasets ERP controlados y generar artefactos reproducibles por `run_id`.
- Ejecutar catálogo antifraude sobre modelos `P2P` y `O2C`.
- Seleccionar hipótesis y tests mediante el flujo multiagente validado del proyecto.
- Producir resultados trazables: `findings`, `scores`, `explanations`, `second_level_analysis` y drilldown seguro.
- Operar el sistema tanto por CLI/cloud como por capa de aplicación (`FastAPI` + `Streamlit`).
- Mantener evidencia verificable mediante tests, artefactos de run y documentación técnica.

## 3. No-goals

Estos puntos quedan explícitamente fuera del core del TFG:

- No se expone SQL libre al usuario final.
- No se implementa generación automática de tests antifraude por LLM como capacidad abierta.
- No se construye un RAG corporativo completo; la KB local se mantiene como extensión opcional/PoC acotada.
- No se persigue cobertura funcional universal sobre cualquier ERP o cualquier tabla SAP fuera de los modelos soportados.
- No se convierte la UI en una herramienta de auditoría generalista; la interfaz está orientada a demo operativa e investigación guiada del sistema.

## 4. Entregables por sprint / fase

### Fase 1

- Ingesta reproducible a DuckDB.
- Data dictionary mínimo y validación técnica del dataset.
- Catálogo inicial de tests antifraude.
- Reporting y drilldown base.

### Fase 2

- Extensión del catálogo P2P.
- Soporte O2C.
- Grafo multiagente con planning, explicaciones, scoring y persistencia de artefactos.

### Fase 3

- Taxonomía de fraude y alineación hipótesis -> tests -> evidencia.
- Evaluación/comparación cuantitativa y baseline.
- Observabilidad con LangSmith.
- Cloud AWS operativo sobre ECS/Fargate.
- Capa de aplicación con `FastAPI` y UI `Streamlit`.

## 5. Criterios de éxito

Se considera que el alcance está cubierto si se cumple lo siguiente:

- Existe un comando o flujo reproducible que carga dataset, ejecuta análisis y genera artefactos por `run_id`.
- Los tests antifraude de `P2P` y `O2C` se ejecutan con evidencias verificables.
- La selección visible de tests y la ejecución real quedan alineadas.
- El sistema genera resultados legibles y trazables para findings, scoring, explicaciones y drilldown.
- Cloud, API y UI funcionan sobre el mismo backend analítico sin romper los contratos del grafo.
- La evidencia queda soportada por tests, documentación y artefactos de run.

## 6. Relación con DoR / DoD

La gobernanza de trabajo y el criterio de "hecho" se detallan en:

- [project_governance.md](./project_governance.md)

## 7. Checklist de revisión de alcance

Antes de cerrar una iteración se revisa:

- ¿El cambio aporta valor a la cadena dataset -> hipótesis -> tests -> ejecución -> explicación?
- ¿Introduce una dependencia o feature fuera de los no-goals?
- ¿Hay evidencia ejecutable: test, artefacto o verificación documentada?
- ¿La documentación visible al usuario final está alineada con el estado real del proyecto?
