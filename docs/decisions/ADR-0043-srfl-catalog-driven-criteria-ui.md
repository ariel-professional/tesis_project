# ADR-0043 — UI SRFL dirigida por catálogo de criterios

- Estado: accepted
- Fecha: 2026-09-17
- Objetivo: OBJ-17

## Decisión

El catálogo Python es la única autoridad para los criterios SRFL v2 disponibles.
El gateway conserva el comando nominado `layout.decision_criteria` y el host
React expone un descriptor tipado. La UI renderiza descriptores y asocia editores
por `required_inputs`, no por identificadores de funciones.

`DecisionModelV2.selected_objectives` conserva referencias únicas `{id, version}`.
Al leer configuraciones v2 anteriores sin ese campo se deriva desde las entradas
históricas; toda serialización nueva lo incluye. Python rechaza referencias
desconocidas, duplicadas o sin sus insumos requeridos.

`core-layout-count`, `rel-matrix` y `flow-matrix` son los insumos soportados en
este corte. Un descriptor con otro insumo permanece visible pero deshabilitado y
diagnosticado, para que una extensión no se oculte ni active un editor incorrecto.

## Consecuencias

Agregar un criterio que reutilice estos insumos sólo requiere incorporarlo al
catálogo Python. La matriz genérica vive en `domain-ui-kit`; REL y flujo siguen
siendo adaptadores de dominio responsables de sus datos y validaciones.
