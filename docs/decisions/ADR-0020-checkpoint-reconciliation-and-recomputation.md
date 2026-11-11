# ADR-0020 — Checkpoint reconciliation and automatic recomputation

- Estado: accepted


- Objetivos afectados: OBJ-12
- Requisitos afectados: RP-05, RP-07, RP-08, RPE-02, RPE-04, RPE-06, RNF-02
- Resuelve: F-004, F-005 y F-016
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, OBJ-12; `docs/reference/contracts/IMPLEMENTATION_SPEC_AI.md`, reglas de reconciliación



## Contexto

La implementación solo reutilizaba StageResults ya referenciados por
`pipeline.json` y no validaba integralmente sus artefactos. Esto no cubría las
ventanas de interrupción del orden durable ni la corrupción posterior.

## Alternativas consideradas

Se evaluaron fallar ante toda incoherencia, reparar únicamente manifests o
recalcular automáticamente desde el primer checkpoint no íntegro.

## Decisión

Resume inspecciona StageResults numerados además de manifests. Adopta resultados
terminales íntegros que quedaron por delante del pipeline, repara manifests
atrasados y determina el primer stage no reutilizable. Ese stage y todos sus
dependientes vuelven a pending y se recalculan. Los intentos anteriores se
conservan cuando el StageResult es parseable; un StageResult corrupto no puede
aportar historia confiable y es reemplazado durante el nuevo intento.

La integridad incluye schema, stage/status/outcome, ArtifactRef, hash, tamaño,
identidad de instancia, convención y reglas de ciclo de vida. La ausencia del
candidato es válida si una instancia canónica íntegra ya lo reemplazó; si stage
03 debe repetirse, el límite retrocede a stage 02. Config/hash/version
incompatibles bloquean resume. Una discrepancia de procedencia detectada por
stage 08 falla con `INTEGRITY_ERROR` y nunca genera match/mismatch.

## Justificación

La recomputación determinista recupera interrupciones reales sin pedir al
usuario que reconstruya un run, y conserva la autoridad del workspace sin
inventar evidencia. Un reconciliador específico mantiene el flujo visible y
evita introducir un motor genérico de workflows.

## Consecuencias

- Artefactos corruptos/no confirmados desde el límite se reemplazan.
- Un reporte dañado recalcula solo stage 10.
- La suite debe inyectar cada ventana de commit e integridad.
- La política de retención general continúa abierta; esta ADR solo gobierna
  evidencia necesaria para reparar el run solicitado.

## Trazabilidad

F-004/F-005/F-016 y decisión de recomputación automática aprobada para OBJ-12.

