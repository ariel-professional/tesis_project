# ADR-0011 — CLI, events, and inspection output

- Estado: accepted


- Objetivos afectados: OBJ-0, OBJ-1, OBJ-8
- Requisitos afectados: RC-01 a RC-07, RPE-08
- Resuelve: BLOCK-007 y payloads pendientes de OPEN-EVENT-CATALOG
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 2 (`public_contract_catalog`), y `docs/contracts/public_contract_catalog.md`, sección 5



## Contexto

El catálogo de nombres no fijaba payloads ni la salida exacta de comandos no ejecutores.

## Alternativas consideradas

Snapshots completos, mensajes ad hoc, o envelopes pequeños tipados y vistas de inspección separadas.

## Decisión

Se aprueban los payloads mínimos, stdout de máquina, stderr humano, las dos vistas de inspección y las reglas de salida por comando. Toda presentación humana será en inglés.

## Justificación

Evita que eventos se conviertan en una segunda fuente de verdad y mantiene stdout automatizable.

## Consecuencias

`save-experiment` exitoso no emite stdout; inspección NDJSON emite exactamente una línea; el único stdout humano es su formato explícito.

## Trazabilidad

ADR-0004, ADR-0005; catálogo público, sección 5.
