# ADR-0001 — Autoridad documental y archivo maestro separado

- Estado: accepted


- Objetivos afectados: OBJ-1 a OBJ-9
- Requisitos afectados: todos los del Incremento 1
- Resuelve: relación entre el contrato fuente y `first_increment.spec.md`
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, secciones 0–1



## Contexto

El repositorio tenía un contrato operativo derivado exclusivamente de `FUENTE_DE_VERDAD_IA.md` y un plan técnico posterior, `first_increment.spec.md`. Era necesario decidir cuál controlaría el comportamiento observable y dónde registrar decisiones nuevas sin atribuirlas falsamente a la fuente histórica.

También se evaluó incorporar todas las resoluciones posteriores dentro de `operative_contract.instructions.md`, pero ese archivo declara que deriva exclusivamente de la fuente y conserva decisiones ausentes como abiertas.

## Alternativas consideradas

1. Dar prioridad general a `first_increment.spec.md`.
2. Modificar el contrato operativo derivado para incorporar decisiones posteriores.
3. Mantener intactos los documentos de procedencia y crear un archivo maestro separado que clasifique y coordine sus reglas.

## Decisión

El comportamiento observable se rige por las reglas `SOURCE_LOCKED` del contrato operativo. `first_increment.spec.md` controla solamente stack y estrategia técnica cuando no existe conflicto.

Las decisiones posteriores aprobadas se registran como `APPROVED_NOW` en `increment_1_master.instructions.md`. La fuente y el contrato derivado no se reescriben para simular que esas decisiones ya existían.

## Justificación

La separación preserva trazabilidad y permite distinguir reglas de origen, aprobaciones posteriores, elecciones técnicas y asuntos aún no resueltos. También evita que una recomendación de librería cambie accidentalmente estados, schemas, persistencia o semántica de dominio.

## Consecuencias

- Todo agente debe aplicar el mapa de autoridad antes de implementar.
- Una contradicción se analiza primero por clase de decisión.
- El master es la autoridad para las resoluciones posteriores y el plan por objetivos.
- Los snapshots históricos permanecen auditables y no reciben decisiones nuevas.

## Trazabilidad

- `instructions.agent/00_READ_FIRST.instructions.md`
- `instructions.agent/increment_1_master.instructions.md`, secciones 0–1
- `docs/reference/contracts/IMPLEMENTATION_SPEC_AI.md`, sección 0
- `docs/archive/plans/first_increment.spec.md`
