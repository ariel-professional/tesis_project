# ADR-0003 — Identificadores, timestamps y enteros grandes

- Estado: accepted


- Objetivos afectados: OBJ-1, OBJ-3, OBJ-4, OBJ-6, OBJ-7 y OBJ-8
- Requisitos afectados: RF-01, RF-02, RF-13, RPE-01, RPE-02, RC-07, RNF-02 y RNF-03
- Resuelve: OPEN-IDENTIFIERS y OPEN-TIMESTAMPS
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 3.2



## Contexto

La fuente requería identificadores y timestamps en manifests, resultados, eventos y cancelación, pero no definía su sintaxis, precisión, generación o política de colisiones. También era necesario conservar conteos exactos sin pérdida en consumidores JSON comunes.

## Alternativas consideradas

1. Identificadores libres suministrados por el usuario y timestamps dependientes de la plataforma.
2. Identificadores secuenciales administrados por cada workspace.
3. Slugs controlados para experimentos, UUID v4 para runs y timestamps UTC canónicos.

## Decisión

- `experiment_id` es un slug ASCII en minúsculas de 1 a 64 caracteres y cumple `^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$`.
- `run_id` es un UUID v4 canónico en minúsculas generado por la aplicación.
- Una colisión nunca sobrescribe evidencia: los IDs generados se regeneran y los proporcionados se rechazan.
- Los timestamps usan RFC 3339, UTC, milisegundos y sufijo `Z`.
- Los enteros de 0 a `2^53-1` pueden ser números JSON; los mayores se serializan como cadenas decimales canónicas.

## Justificación

Los slugs permiten nombres de experimento legibles y confinables. UUID v4 evita coordinación global entre workspaces. Una única representación temporal y de enteros evita divergencias entre Python y futuros consumidores JavaScript.

## Consecuencias

- OBJ-1 debe implementar validadores y pruebas de canonicalidad.
- Ningún comando puede sobrescribir por colisión.
- La serialización de conteos debe preservar precisión aunque cambie su tipo wire según la magnitud.

## Trazabilidad

- `instructions.agent/increment_1_master.instructions.md`, sección 3.2
- `docs/reference/contracts/IMPLEMENTATION_SPEC_AI.md`, `OPEN-IDENTIFIERS` y `OPEN-TIMESTAMPS`
