# ADR-0017 — Modular monolith boundaries

- Estado: accepted


- Objetivos afectados: OBJ-10
- Requisitos afectados: RNF-01, RP-01, RP-05, RPE-06, RC-01 a RC-07
- Resuelve: no aplica
- Regla normativa: `instructions.agent/objectives/OBJ-10_technical_simplification.instructions.md`



## Contexto

El Incremento 1 quedó aceptado, pero el orquestador, los servicios y los
adaptadores acumularon responsabilidades y dependencias internas difíciles de
seguir. La mejora debe preservar todos los contratos observables ya cerrados.

## Alternativas consideradas

Se consideraron una reescritura por capas estrictas, refactors exclusivamente
locales y un monolito modular evolucionado por slices verificables.

## Decisión

Se adopta un monolito modular. `models`, `domain` y `engines` constituyen la
base; `persistence` y `runner` implementan infraestructura; `application`
coordina casos de uso; `reporting` renderiza modelos ya construidos; `cli` es
el composition root y adaptador público. Las dependencias inversas se impiden
mediante pruebas estáticas del árbol de imports.

El pipeline conserva una secuencia explícita. Se separan coordinación,
handlers de stages, journaling durable y acceso al run sin introducir un motor
genérico de workflows.

## Justificación

Esta estructura reduce acoplamiento y duplicación manteniendo visible el flujo
contractual. Permite migraciones pequeñas con schemas y suites como red de
seguridad.

## Consecuencias

- Los imports internos cambian, pero no las interfaces JSON, CLI ni workspace.
- Se agregan objetos internos de repositorio, layout, reporte y journaling.
- Los módulos históricos pueden actuar temporalmente como fachadas.
- Toda desviación observable requiere una decisión separada.

## Trazabilidad

Solicitud de simplificación técnica aprobada el 2026-08-10; ADR-0016; suites
`STATE`, `FAILURE`, `CANCEL`, `RESUME`, `CLI-CONTRACT` y `SECURITY`.

## Aclaración posterior

ADR-0018 documenta la arquitectura funcional de cuatro bloques a la que estas
fronteras técnicas están subordinadas. No modifica la dirección de imports ni
los contratos decididos aquí.
