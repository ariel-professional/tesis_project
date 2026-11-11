# ADR-0047 — Diseño de control y contexto documental en resultados SRFL

**Estado:** accepted  
**Fecha:** 2026-09-22  
**Objetivo:** OBJ-17

## Contexto

SRFL 2.0 rechazaba todo diseño sin restricciones obligatorias, aunque el dominio
formal y el CORE admiten el bosque vacío. Además, la lista Desktop ocultaba el
nombre durable de cada ejecución y la vista de resultados v2 no recuperaba los
antecedentes confirmados por ADR-0040.

## Decisión

- SRFL 2.0 admite un único diseño con `base_component_ids` vacío. Ese diseño se
  identifica como control; los restantes deben conservar al menos una restricción
  obligatoria.
- Se mantiene la regla de ADR-0032: todos los componentes fuera de la base son
  candidatos. Por ello el control genera `2^|C|` selecciones e incluye el caso
  sin restricciones; no es un caso aislado especial.
- La lista Desktop presenta `display_name` ya persistido en el manifiesto y deja
  el UUID completo como referencia secundaria. No cambia el protocolo.
- Los resultados v2 recuperan una sola vez la configuración desde
  `study.documentation`. El detalle relaciona en memoria diseño, componentes,
  REL, políticas y matrices con cada arista seleccionada.
- La documentación no se copia dentro de cada caso ni amplía `result.json`.

## Compatibilidad

SRFL 1.0 permanece sin cambios. Toda configuración SRFL 2.0 previamente válida
continúa siéndolo y conserva su identidad. La ampliación sólo acepta una forma
antes rechazada; más de un control es inválido en React y en Python.

