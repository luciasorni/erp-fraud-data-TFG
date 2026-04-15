from __future__ import annotations

import streamlit as st

from app.ui.components.header import configure_page, render_divider, render_page_header, render_section_heading
from app.ui.utils.session_state import init_session_state


def main() -> None:
    configure_page(page_title="Cómo funciona")
    init_session_state()
    render_page_header(
        title="Cómo funciona el análisis",
        subtitle="Guía rápida para entender qué hace la aplicación, qué significan P2P y O2C y cómo leer los resultados.",
    )

    render_section_heading(
        title="Qué analizan P2P y O2C",
        subtitle="El sistema trabaja sobre dos familias de proceso ERP para detectar señales de fraude o anomalía con lógica diferente.",
    )
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown(
            """
            **P2P · Procure to Pay**

            Revisa el ciclo de compras y pagos. Aquí suelen aparecer señales como:
            - duplicados de facturas o postings
            - importes anómalos por proveedor
            - patrones extraños de aprobación o contabilización
            - riesgo en proveedores, documentos y pagos
            """
        )
    with col2:
        st.markdown(
            """
            **O2C · Order to Cash**

            Revisa el ciclo comercial y de cobro. Aquí suelen aparecer señales como:
            - anomalías en facturación
            - secuencias temporales incoherentes
            - entregas, cobros o documentos fuera de patrón
            - inconsistencias entre pedido, factura y cobro
            """
        )

    render_divider()
    render_section_heading(
        title="Qué hace un run",
        subtitle="Un análisis cloud en modo graph sigue una secuencia orientada a hipótesis, evidencia y explicación.",
    )
    st.markdown(
        """
        1. Se carga el dataset ERP y su contexto.
        2. El sistema genera hypotheses iniciales sobre posibles patrones de fraude.
        3. Selecciona los tests más relevantes para ese contexto.
        4. Ejecuta los tests y produce findings.
        5. Resume la señal global mediante scoring.
        6. Genera explicaciones narrativas y recomendaciones de investigación.
        7. Permite drilldown seguro sobre un hallazgo concreto.
        """
    )

    render_divider()
    render_section_heading(
        title="Cómo leer los resultados",
        subtitle="Cada bloque responde a una pregunta distinta del proceso de investigación.",
    )
    st.markdown(
        """
        - **Hypotheses**: qué sospechas o líneas de análisis surgieron.
        - **Selected tests**: qué controles se eligieron para contrastar esas hipótesis.
        - **Findings**: qué señales concretas se detectaron en los datos.
        - **Score**: resumen final de la señal principal del run. Es normal que aparezca una sola salida agregada si el sistema sintetiza la priorización final en un único scoring principal.
        - **Explicación**: por qué el sistema considera que el caso merece revisión.
        - **Recomendaciones**: siguientes pasos, pruebas sugeridas y contraste adicional.
        - **Comparativas**: insights del second-level explainer sobre por qué el caso destaca frente al patrón esperado o frente a otros runs comparados.
        """
    )

    render_divider()
    render_section_heading(
        title="Qué papel tienen el explainer y el second-level explainer",
        subtitle="La narrativa principal y la explicación comparativa no cumplen la misma función.",
    )
    st.markdown(
        """
        - **Explainer**: traduce findings y scoring a una explicación comprensible del caso.
        - **Second-level explainer**: añade una capa de contexto adicional. Compara, contextualiza, propone acciones y explica por qué un caso destaca frente al baseline o frente a otros runs disponibles.
        """
    )


if __name__ == "__main__":
    main()
