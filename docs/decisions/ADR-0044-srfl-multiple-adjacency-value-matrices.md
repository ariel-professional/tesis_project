# ADR-0044 — Múltiples matrices de valor de adyacencias en SRFL 2.0

**Estado:** accepted  
**Fecha:** 2026-09-19  
**Objetivo:** OBJ-17

## Contexto

SRFL 2.0 sólo admitía una matriz de flujo, siempre maximizada. Eso impedía comparar en un mismo experimento magnitudes independientes como movimientos, costo, riesgo o beneficio.

## Decisión

`decision_model.adjacency_flow` admite, sin cambiar `schema_version` ni `domain.version`, dos representaciones mutuamente excluyentes:

- el objeto histórico `FlowMatrix`, conservado para lectura, identidad y resultados existentes;
- una lista no vacía de matrices cuantitativas con identificador y nombre únicos, descripción, objetivo `maximize|minimize`, unidad, período opcional, fuente, direccionalidad y valores decimales exactos no negativos.

Cada matriz nueva genera una dimensión Pareto `adjacency-<matrix-id>`. Su valor es la suma de las celdas correspondientes a las adyacencias obligatorias del caso. Una matriz dirigida suma ambos sentidos del par; una no dirigida usa su celda canónica. No se ponderan ni agregan las dimensiones entre sí.

Los resultados históricos conservan `captured_flow`. Los nuevos agregan `adjacency_values[]` con total, dirección, unidad y contribuciones por par. Si falta una observación concluyente, la clasificación global sigue siendo inconclusa.

El catálogo declara `direction_mode` y `repeatable_input`. El gateway pasa al protocolo global `1.2`; las aplicaciones SRFL 1.0 y 2.0 continúan registradas por el mismo host.

## Compatibilidad

Esta decisión reemplaza parcialmente el supuesto de matriz de flujo única de ADR-0041 y la dirección fija expuesta por ADR-0043. No reescribe configuraciones, proyecciones ni resultados existentes. La conversión del objeto histórico a una matriz editable ocurre sólo en memoria; una nueva confirmación produce la representación múltiple.

## Consecuencias

La validación exige matrices completas, metadatos operativos, decimales exactos, ausencia de duplicados y al menos un valor positivo sobre una restricción candidata. La UI reconcilia todas las matrices al cambiar estaciones y muestra alias y dirección en revisión, tablas, gráficos y detalle.
