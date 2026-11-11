# ADR-0006 — Protocolo local de cancelación

- Estado: accepted


- Objetivos afectados: OBJ-1 y OBJ-7
- Requisitos afectados: RP-06, RP-08, RC-03, RNF-04 y RNF-05
- Resuelve: OPEN-CONTROL-WIRE-PROTOCOL
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 3.5



## Contexto

La fuente exigía cancelar un run activo mediante un canal local controlado por el runner, pero no definía transporte, identidad del endpoint, autenticación, mensajes ni reglas de idempotencia.

## Alternativas consideradas

1. Permitir que el comando externo modificara directamente los manifests del run activo.
2. Abrir un listener de red autenticado por un secreto de aplicación.
3. Usar IPC local protegido por el sistema operativo y mantener el lock como única prueba de actividad.

## Decisión

Unix usa un socket de dominio local y Windows una named pipe. No se abre un listener de red. El endpoint se deriva de la ruta canónica del workspace y el `run_id` mediante SHA-256 y se restringe al usuario propietario.

Cada conexión transporta una solicitud JSON y una respuesta JSON estrictas, delimitadas por salto de línea. La primera cancelación aceptada se persiste antes de responder y gana de forma idempotente. El comando externo nunca modifica manifests de un run cuyo lock está ocupado.

Los schemas, estados de respuesta y orden de procesamiento son los declarados en la sección 3.5 del master.

## Justificación

El protocolo conserva un único escritor, evita exponer una superficie de red y permite distinguir entrega, persistencia y finalización cooperativa o forzada.

## Consecuencias

- OBJ-1 versiona los mensajes estrictos.
- OBJ-7 debe implementar y probar permisos `0600` en Unix y ACL del usuario actual en Windows.
- La existencia del endpoint no indica actividad; el lock ocupado continúa siendo la autoridad.
- Un canal inaccesible con lock ocupado produce `RUN_CONTROL_UNAVAILABLE` sin mutar el workspace.

## Trazabilidad

- `instructions.agent/increment_1_master.instructions.md`, sección 3.5
- `docs/reference/contracts/IMPLEMENTATION_SPEC_AI.md`, `OPEN-CONTROL-WIRE-PROTOCOL`
