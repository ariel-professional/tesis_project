# ADR-0012 — Runner-worker framed protocol

- Estado: accepted


- Objetivos afectados: OBJ-0, OBJ-1, OBJ-5, OBJ-7
- Requisitos afectados: RF-09, RF-10, RP-06, RNF-04
- Resuelve: BLOCK-008
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 2 (`public_contract_catalog`), y `docs/contracts/public_contract_catalog.md`, sección 6



## Contexto

El contrato exigía workers aislados pero no definía framing, mensajes ni manejo de respuestas incompletas.

## Alternativas consideradas

NDJSON, objetos de multiprocessing implícitos, o frames de longitud fija con JSON estricto.

## Decisión

Se adopta prefijo unsigned big-endian de cuatro bytes, una solicitud/respuesta estricta y canal separado de un byte para cancelación cooperativa. El runner limita y valida antes de confirmar.

## Justificación

El framing detecta truncamiento y permite aplicar un límite antes de decodificar sin acoplar el contrato a pickle.

## Consecuencias

Terminación, protocolo o payload inválido son fallos generales y nunca resultados científicos.

## Trazabilidad

Catálogo público, sección 6.
