# ADR-0009 — Exhaustive configuration and schema contract

- Estado: accepted


- Objetivos afectados: OBJ-0, OBJ-1
- Requisitos afectados: RF-01 a RF-07, RPE-01 a RPE-05, RNF-02, RNF-03
- Resuelve: BLOCK-001 a BLOCK-005 y OPEN-JSON-SCHEMAS
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 2 (`public_contract_catalog`), y `docs/contracts/public_contract_catalog.md`, secciones 1–4
- Supersede: ADR-0002


## Contexto

La política base no definía campos, variantes, nulabilidad ni la frontera entre configuración y validación del pipeline.

## Alternativas consideradas

Validar aristas al guardar, aceptar configuraciones permisivas, o cerrar modelos estrictos preservando los errores de dominio hasta su stage.

## Decisión

Se aprueba el catálogo exhaustivo 1.0.0. La configuración valida estructura y límites; stage 3 valida aristas y stage 4 estructura. Los floats inline se rechazan por la canonicalización sin floats. Se fijan fuentes, métodos siempre presentes, único default, archivos directos y generadores `builtin-v1`.

## Justificación

La frontera conserva los diagnósticos contractuales sin permitir configuraciones estructuralmente ambiguas y permite generar schemas definitivos.

## Consecuencias

OBJ-1 debe implementar exactamente el catálogo y detectar drift. No se agregan defaults ni familias sin una nueva decisión.

## Trazabilidad

Cuestionario aprobado del plan de cierre; `docs/contracts/blocking_questions.md`; catálogo público, secciones 1–4.
