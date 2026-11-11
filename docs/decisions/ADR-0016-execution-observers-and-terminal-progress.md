# ADR-0016 — Execution observers and interactive terminal progress

- Estado: accepted
- Fecha: 2026-08-06

- Objetivos afectados: OBJ-5, OBJ-6, OBJ-8 y OBJ-9
- Requisitos afectados: RF-09, RF-10, RP-01, RP-06, RC-01 a RC-07, RNF-01 y RNF-04
- Resuelve: no aplica
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 3.8; `docs/contracts/public_contract_catalog.md`, secciones 5.1 y 6



## Contexto

La CLI emitía eventos de máquina correctos, pero no guiaba a una persona
durante los diez stages ni mostraba progreso de los cálculos prolongados. Unir
esa presentación directamente a Typer habría acoplado el pipeline a una UI y
dificultado agregar consumidores futuros.

## Alternativas consideradas

Se consideraron imprimir directamente desde el pipeline, ampliar los eventos
públicos con actualizaciones frecuentes, o publicar notificaciones internas
neutrales consumidas por adaptadores independientes.

## Decisión

Pipeline y servicios publican notificaciones internas mediante un puerto
`ExecutionObserver`. NDJSON y la terminal son adaptadores separados; un
adaptador nulo y uno compuesto completan la base. La terminal muestra progreso
en inglés solo cuando `stderr` es TTY. Los workers pueden enviar contadores por
un canal efímero separado sin cambiar su request ni su única respuesta.

No se define un protocolo de Electron. La telemetría no se persiste, no se
convierte en evento público, no extiende timeouts y no es evidencia. Solo se
muestra porcentaje cuando existe un total verificable.

## Justificación

El puerto mantiene la aplicación independiente de la UI, conserva stdout
automatizable y permite sumar adaptadores sin duplicar reglas del pipeline.

## Consecuencias

- Rich queda limitado al adaptador de terminal.
- Los fallos visuales no cambian el resultado científico.
- Los eventos y schemas públicos permanecen estables.
- Un futuro adaptador externo deberá tomar una decisión propia sobre transporte
  y versionado; esta ADR no anticipa Electron ni React.

## Trazabilidad

Aprobación explícita del responsable del proyecto el 2026-08-06; ADR-0004,
ADR-0005, ADR-0011, ADR-0012 y ADR-0015; suites `CLI-CONTRACT`, `STATE`,
`CANCEL`, `RESUME` y workers.
