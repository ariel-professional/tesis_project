# ADR-0037 — Fail-fast de ejecuciones agrupadas ante fallo CORE

**Estado:** accepted  
**Fecha:** 2026-09-03

## Contexto

Una ejecución agrupada continuaba generando casos después de que un hijo CORE terminara
`failed`. Un fallo sistémico —por ejemplo, un timeout de worker— podía repetirse para cada
combinación, consumiendo tiempo y ocultando el primer diagnóstico durable relevante.

## Decisión

- Después de persistir el estado final del intento CORE, `DomainApplication` detiene la
  ejecución agrupada si ese intento termina `failed`.
- El error de dominio identifica el ordinal del caso, su `core_run_id`, el primer stage CORE
  fallido y su diagnóstico durable cuando existe.
- El manifest agrupado se confirma como `failed`; no se solicita otra combinación.
- La cancelación conserva su semántica propia: un hijo CORE `cancelled` termina el grouped run
  como `cancelled`, no como `failed`.

## Consecuencias

Los casos e intentos ya confirmados se preservan y no se agregan schemas, eventos gateway ni
campos persistidos. La regla es infraestructura común y aplica a SRFL e inspection-route.
