# ADR-0039 — Plantillas de usuario y compatibilidad de proyecciones SRFL

**Estado:** accepted  
**Fecha:** 2026-09-07

## Contexto

Desktop sólo enumeraba ejemplos estáticos del checkout. Además, agregar la descripción
opcional al estudio SRFL hizo que la validación recalculara la identidad de proyecciones
anteriores incluyendo `description: null`, aunque el documento original no contenía esa clave.

## Decisión

- Conservar los ejemplos incluidos y agregar plantillas creadas por el usuario bajo
  `workspace/domain_templates/<domain_experiment_id>.json`.
- Validar siempre la configuración con el adaptador de dominio antes de persistirla.
- Usar su identidad content-addressed para que guardar repetidamente la misma definición sea
  idempotente.
- Extender de forma compatible el protocolo gateway `1.0` con `templates.save` y
  `templates.set_for_run`; no se agrega una versión de capability.
- Permitir marcar una definición desde la revisión y activar o desactivar como plantilla la
  configuración asociada a cualquier ejecución de dominio.
- Aceptar en proyecciones SRFL tanto la identidad canónica actual como la identidad histórica
  calculada omitiendo `study.description` cuando ésta es nula. No se reescriben ni migran
  archivos históricos.

## Consecuencias

Las plantillas del usuario sobreviven al cierre de Electron y pueden eliminarse sin afectar la
proyección ni los runs que les dieron origen. La compatibilidad heredada queda limitada a la
única diferencia conocida (`description` ausente) y todas las demás validaciones permanecen
estrictas.
