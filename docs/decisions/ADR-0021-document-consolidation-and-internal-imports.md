# ADR-0021 — Consolidación documental e imports internos

- Estado: accepted


- Objetivos afectados: OBJ-13
- Requisitos afectados: ninguno; preservación transversal de RF/RP/RPE/RC/RNF
- Resuelve: no aplica
- Regla normativa: `instructions.agent/00_READ_FIRST.instructions.md`, `instructions.agent/increment_1_master.instructions.md` y `docs/history/PROJECT_RECORD.md`
- Supersede: ADR-0001 y ADR-0008 solo respecto de la ubicación de historia detallada y objetivos completados


## Contexto

Las iteraciones 0–12 dejaron instrucciones por objetivo, auditorías, planes
reemplazados y varias fuentes que repetían el estado. El código también
conservaba fachadas y reexports exclusivamente por imports Python históricos,
aunque el contrato público sólo reconoce CLI, eventos, schemas y workspace.

## Alternativas consideradas

1. Conservar todo y añadir nuevos índices.
2. Automatizar una política de retención y compatibilidad interna.
3. Resumir historia, reducir la autoridad activa y reorganizar internals sin
   cambiar contratos observables.

## Decisión

- El flujo operativo comienza en `00_READ_FIRST`, consulta el ledger para el
  estado y carga contratos detallados sólo cuando la superficie tocada lo exige.
- `PROJECT_RECORD.md` conserva el resumen técnico de objetivos, auditorías,
  remediaciones, métricas, retiros y pendientes externos.
- Se conservan íntegros `bitácora.md`, todas las ADR, el snapshot fuente y el
  contrato histórico derivado.
- Se retiran auditorías y planes detallados ya resumidos, preguntas resueltas e
  instrucciones individuales de objetivos terminados.
- No existe compatibilidad pública para rutas o imports Python internos. Pueden
  retirarse tras auditar consumidores runtime, tests, schemas, entry points,
  imports dinámicos, trazabilidad y responsabilidad contractual.
- Esta decisión no crea limpieza automática ni resuelve `OPEN-RETENTION`.

## Justificación

Una fuente única para estado y un recorrido documental corto reducen el riesgo
de obedecer información histórica como si fuera vigente. Retirar fachadas
internas sin consumidores hace visibles las dependencias reales y evita que la
compatibilidad accidental bloquee mejoras de estructura.

## Consecuencias

Los enlaces históricos dentro de ADR o referencias preservadas pueden apuntar a
rutas retiradas y deben leerse como evidencia de su época. Código externo que
hubiera importado internals no documentados deberá migrar a las rutas vigentes.
Los contratos observables `1.0.0` permanecen sin cambios.

## Trazabilidad

OBJ-13; `docs/history/PROJECT_RECORD.md`; prueba arquitectónica; aceptación
integral y comparación byte a byte de los 19 schemas.
