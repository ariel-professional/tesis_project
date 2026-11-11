# ADR-0008 — Organización documental, ledger de estado y OBJ-0

- Estado: accepted


- Objetivos afectados: OBJ-0 a OBJ-9
- Requisitos afectados: todos, de forma indirecta
- Resuelve: ubicación documental, duplicación del contrato y preparación previa de OBJ-1
- Regla normativa: `instructions.agent/00_READ_FIRST.instructions.md`, `instructions.agent/increment_1_master.instructions.md` e `instructions.agent/objective_status.instructions.md`



## Contexto

La auditoría integral encontró seis documentos en la raíz, dos copias línea por línea del mismo contrato, ausencia de un ledger de objetivos y un `OBJ-1` marcado como listo aunque todavía requería cerrar schemas públicos observables.

## Alternativas consideradas

1. Mantener todos los documentos en la raíz y confiar en la precedencia explicada por el router.
2. Comenzar `OBJ-1` y cerrar los schemas durante la implementación.
3. Separar referencias, archivos históricos e instrucciones vigentes, retirar la copia duplicada y agregar un objetivo documental previo.

## Decisión

Los snapshots y contratos derivados se preservan bajo `docs/reference/`; el plan técnico reemplazado pasa a `docs/archive/`; las ADR viven en `docs/decisions/` y las preguntas de contrato en `docs/contracts/`.

Se crea `objective_status.instructions.md` como única fuente mutable del avance. Se agrega `OBJ-0` para cerrar decisiones públicas antes de habilitar `OBJ-1`.

## Justificación

La separación reduce autoridad accidental y evita divergencia entre copias. Un ledger independiente permite actualizar avance sin reescribir la planificación normativa. `OBJ-0` impide que el agente convierta campos conocidos pero incompletos en schemas definitivos inventados.

## Consecuencias

- `OBJ-1` queda pendiente hasta completar `OBJ-0`.
- El contrato derivado se lee desde `docs/reference/contracts/IMPLEMENTATION_SPEC_AI.md`.
- `instructions.agent/operative_contract.instructions.md` deja de existir porque duplicaba íntegramente el contrato canónico.
- Los documentos preservados no reciben decisiones posteriores.
- La estructura Python, schemas y CI se crean únicamente al habilitar `OBJ-1`.

## Trazabilidad

- `docs/contracts/blocking_questions.md`
- `instructions.agent/objectives/OBJ-0_contract_closure.instructions.md`
- `instructions.agent/objective_status.instructions.md`
- `docs/reference/README.md`
- `docs/archive/plans/README.md`
