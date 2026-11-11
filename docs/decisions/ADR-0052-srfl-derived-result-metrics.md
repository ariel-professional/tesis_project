# ADR-0052 — Consultas derivadas de métricas SRFL

**Estado:** accepted  
**Fecha:** 2026-10-02

## Contexto

SRFL 2.0 y 2.1 necesitan análisis descriptivos e interactivos sobre resultados ya
confirmados. En alto rendimiento, los casos viven en artefactos indexados y no
deben cargarse en React. `result.json` representa evidencia científica confirmada
y no debe reescribirse para incorporar análisis derivados.

## Decisión

- Agregar el comando nominado `domain_run.metrics` al protocolo desktop `1.5`.
- Las solicitudes identifican el run y la métrica; incluyen diseño, criterio,
  caso y cursor según la consulta. Las respuestas incluyen resumen, estado, total,
  hasta 50 filas y cursor siguiente.
- Python valida identidades contra el run y el resultado confirmado. Las métricas
  leen casos SRFL 2.0/2.1 estándar o artefactos verificados del modo rápido. No
  ejecutan CORE ni escriben `result.json`.
- Los cálculos conservan fracciones exactas, dirección y unidad. Las fronteras
  inconclusas se informan como inconclusas. Los resultados permanecen separados
  por diseño; entre diseños sólo se comparan patrones estructurales.
- Sensibilidad de Pareto se solicita a demanda y se reutiliza temporalmente. El
  renderer recibe páginas acotadas.

## Consecuencias

El protocolo 1.4 queda preservado como schema histórico y el transporte vigente
pasa a 1.5. Schema y tipos se generan desde Pydantic. SRFL 1.0 conserva su vista
histórica. Los análisis derivados no alteran resultados ni conteos CORE.
