# ADR-0019 — Pre-release public contract rebaseline

- Estado: accepted


- Objetivos afectados: OBJ-12
- Requisitos afectados: RF-04, RF-08, RF-12, RF-13, RNF-02, RNF-03
- Resuelve: F-001, F-002, F-006, F-007 y F-013
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, secciones 3.2, 3.6 y OBJ-12; `docs/contracts/public_contract_catalog.md`
- Supersede: ADR-0009 y ADR-0010 solo en las reglas modificadas aquí


## Contexto

La auditoría de conformidad encontró que el contrato 1.0.0 todavía no fue
publicado ni tiene consumidores externos verificables, pero contiene una
taxonomía científica empobrecida, métricas temporalmente imposibles y una
regla Unicode demasiado amplia para candidatos opacos. Existen workspaces
locales de demostración que pueden regenerarse y no deben motivar una capa de
migración permanente.

## Alternativas consideradas

Se evaluaron conservar el runtime actual, crear una versión 2.0.0 con o sin
migración, o corregir el contrato pre-release 1.0.0 antes de publicarlo.

## Decisión

- Se rebasa `schema_version: "1.0.0"` en el lugar; no se implementa migración
  ni compatibilidad garantizada con workspaces anteriores a esta ADR.
- `case_type` usa las seis categorías SOURCE_LOCKED y sus condiciones exactas.
- Stage 09 persiste exactamente ocho resúmenes ordenados del último intento
  confirmado de los stages 01–08. Stage 09 y stage 10 no aparecen en ese
  resumen porque aún no están confirmados cuando se construye.
- Cada resumen identifica stage, número de intento, estado, terminación y
  `AttemptMetrics`. El historial completo permanece en `StageResult.attempts`.
- NFC se aplica a strings semánticos. Los valores y claves dentro de datos
  candidatos opacos se preservan y son byte-sensibles para `run_config_hash`.
- Los modelos validan invariantes wire locales; las invariantes matemáticas
  que requieren instancia se validan en el dominio y en reconciliación.
- En `builtin-v1`, `counter-ascii` es literalmente `"0"`.

## Justificación

Las seis categorías ayudan al análisis experimental por un costo mínimo. Ocho
resúmenes identificados son temporalmente honestos y útiles sin duplicar la
historia. La normalización dirigida conserva reproducibilidad sin alterar una
entrada inválida que debe llegar intacta al stage de diagnóstico. Rebasar una
versión no publicada evita una migración sin usuarios.

## Consecuencias

- Cambian varios schemas bajo `schemas/1.0.0/`.
- Los workspaces locales previos pueden dejar de validar y deben regenerarse;
  la implementación no los modifica automáticamente.
- Un candidato inline que solo difiere en representación Unicode opaca puede
  producir un `run_config_hash` distinto.
- El snapshot histórico permanece inalterado.

## Trazabilidad

Auditoría `source-truth-conformance-2026-08-10`; decisiones confirmadas por el
responsable del proyecto en la planificación de OBJ-12.

