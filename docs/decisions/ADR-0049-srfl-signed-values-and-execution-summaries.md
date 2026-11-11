# ADR-0049 — Valores con signo y resúmenes de ejecución SRFL 2

**Estado:** accepted  
**Fecha:** 2026-09-29  
**Objetivo:** OBJ-17

## Decisión

- Las matrices cuantitativas SRFL 2 admiten decimales exactos negativos, cero y positivos. Maximización y minimización comparan las sumas con signo.
- Una matriz REL formada sólo por U y X es válida. No crea dimensiones de prioridad REL; cada X conserva su política explícita.
- El manifiesto SRFL 2 guarda resúmenes teóricos por diseño, tiempo activo acumulado e inicio del tramo activo. Al reanudar tras una interrupción, el tramo anterior se confirma sólo hasta el último `updated_at` durable.
- Un caso CORE deduplicado pertenece al primer diseño que lo generó (`origins[0]`). Los demás orígenes documentan coincidencias sin cambiar el propietario.
- `domain_run.list` entrega los datos del manifiesto sin `cases`. `generation_progress` puede incluir `valid_selections` y `core_case_started` puede incluir `design_id` para renderizar progreso y origen sin abrir cada caso.

## Compatibilidad

Los campos nuevos del manifiesto tienen defaults para leer ejecuciones SRFL 2 anteriores. Los datos opcionales de eventos no alteran los consumidores existentes. El gateway conserva el protocolo `1.2` y los mismos comandos.
