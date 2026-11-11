# ADR-0007 — Persistencia de métricas y límites explícitos

- Estado: superseded


- Objetivos afectados: OBJ-1, OBJ-5, OBJ-6, OBJ-7 y OBJ-9
- Requisitos afectados: RF-10, RF-12, RP-06, RNF-02 y RNF-04
- Resuelve: OPEN-METRICS-STORAGE y OPEN-DEFAULT-LIMITS
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 3.6

- Superseded by: ADR-0014

## Contexto

La fuente exigía métricas, timeouts, umbrales y límites de tamaño, pero no fijaba su ubicación durable, campos mínimos, rangos ni valores para la suite basal.

## Alternativas consideradas

1. Crear `artifacts/metrics.json` como artefacto independiente.
2. Mantener métricas únicamente en memoria hasta exportar.
3. Consolidarlas en el resultado del stage 09 y exigir límites enteros explícitos en la configuración.

## Decisión

Las métricas consolidadas se persisten dentro del `StageResult` de `09_collect_metrics`. No existe `artifacts/metrics.json`.

Se adoptan las métricas mínimas y los diez campos de límites, rangos y valores basales definidos en la sección 3.6 del master. Los límites deben estar explícitos en la configuración y su ausencia se rechaza.

## Justificación

El stage 09 ya es la unidad contractual responsable de consolidar métricas. Mantenerlas allí evita otro artefacto con autoridad ambigua. Los límites explícitos hacen que cada run sea reproducible y evitan cambios silenciosos entre versiones.

## Consecuencias

- Los reportes derivan las métricas del `StageResult` confirmado.
- Los recursos que la plataforma no pueda observar confiablemente no se inventan.
- El fixture `valid_large_skip_reference_n12` usa `reference_max_n=10`.
- Superar límites generales se clasifica como configuración o datos inválidos sin crear nuevos códigos de dominio basales.

## Trazabilidad

- `instructions.agent/increment_1_master.instructions.md`, sección 3.6
- `docs/reference/contracts/IMPLEMENTATION_SPEC_AI.md`, `OPEN-METRICS-STORAGE` y `OPEN-DEFAULT-LIMITS`
