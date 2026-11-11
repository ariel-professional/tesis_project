# ADR-0005 — Catálogo mínimo y garantías de eventos

- Estado: accepted


- Objetivos afectados: OBJ-1, OBJ-6, OBJ-7 y OBJ-8
- Requisitos afectados: RC-07, RPE-08 y RNF-04
- Resuelve: OPEN-EVENT-CATALOG, excepto los payloads exhaustivos que debe cerrar OBJ-1
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 3.4



## Contexto

La fuente definía un envelope NDJSON y separaba eventos de la evidencia durable, pero no enumeraba eventos, payloads ni garantías de orden y confirmación.

## Alternativas consideradas

1. Emitir eventos ad hoc según cada comando.
2. Tratar el log o los eventos como replay completo del estado.
3. Adoptar un catálogo mínimo versionado, con eventos posteriores a confirmaciones durables y sin garantía de entrega exacta.

## Decisión

El catálogo mínimo contiene `run_created`, `run_started`, `run_resumed`, `run_interruption_detected`, `stage_started`, `stage_terminal`, `cancellation_accepted`, `report_exported`, `run_terminal` y `diagnostic`.

Los eventos terminales se emiten después de confirmar durablemente el estado anunciado. `stage_started` se emite después de reflejar el stage activo en `pipeline.json`. No hay replay ni entrega exactamente una vez; el workspace resuelve discrepancias.

## Justificación

El catálogo cubre el ciclo de vida observable sin duplicar artefactos científicos ni convertir el stream en una segunda fuente de verdad.

## Consecuencias

- OBJ-1 todavía debe cerrar y versionar el payload estricto de cada evento.
- Los payloads contienen referencias o resúmenes acotados, no artefactos completos.
- Una caída puede impedir eventos no confirmados y los consumidores deben reconstruir desde el workspace.

## Trazabilidad

- `instructions.agent/increment_1_master.instructions.md`, sección 3.4
- `docs/reference/contracts/IMPLEMENTATION_SPEC_AI.md`, `OPEN-EVENT-CATALOG`
