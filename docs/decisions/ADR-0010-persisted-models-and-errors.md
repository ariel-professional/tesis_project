# ADR-0010 — Persisted models, results, and errors

- Estado: accepted


- Objetivos afectados: OBJ-0 a OBJ-9
- Requisitos afectados: RF-08 a RF-14, RP-01 a RP-07, RPE-02 a RPE-06, RC-07
- Resuelve: BLOCK-006
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 2 (`public_contract_catalog`), y `docs/contracts/public_contract_catalog.md`, secciones 3–4 y 8



## Contexto

Las entidades conocidas carecían de variantes exhaustivas, intentos, referencias, nulabilidad y códigos enteros estables.

## Alternativas consideradas

Objetos parcialmente presentes, resultados monolíticos, o uniones estrictas por estado con nulabilidad explícita.

## Decisión

Se adoptan las entidades exhaustivas del catálogo, historial completo de intentos, `ValidationResult` embebido, reportes derivados autocontenidos, referencias con hash y tamaño, representación exacta de enteros grandes y el mapa basal 1–14.

## Justificación

Las uniones discriminadas hacen verificable cada estado sin inferencias por ausencia y preservan evidencia de reanudación.

## Consecuencias

Todos los outputs emiten claves nullable. Los errores generales usan símbolos estables y código de dominio nulo. Un mismatch completa el run.

## Trazabilidad

Cuestionario aprobado; catálogo público, secciones 3–4 y 8.
