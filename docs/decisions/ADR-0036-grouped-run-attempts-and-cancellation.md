# ADR-0036 — Intentos CORE y cancelación de runs agrupados

**Estado:** accepted  
**Fecha:** 2026-09-02

## Contexto

Un caso agrupado persistía un único `core_run_id/status`. CORE rechaza reanudar un run
`cancelled`, por lo que ese modelo no puede preservar evidencia y continuar el caso sin perder el
UUID cancelado.

## Decisión

- Rebaselinar los manifests agrupados pre-release de SRFL e inspection-route como `1.0.0`, sin
  migración de workspaces locales.
- Reemplazar los campos escalares por una lista no vacía de
  `CoreRunAttempt {core_run_id,status}`. El intento actual es el último.
- Reutilizar intentos `completed`; ejecutar `created`; usar `CoreCommands.resume` para
  `running/failed`; crear y agregar un run nuevo para `cancelled`.
- Crear un `threading.Event` por operación gateway. `DomainApplication` recibe la consulta
  `is_cancel_requested`; cada dominio decide sus checkpoints y lanza `DomainRunCancelled`.
- SRFL comprueba al entrar en cada nodo DFS e inspection-route entre escenarios. La aplicación
  confirma el manifest como `cancelled` sin pasar por `failed`.
- Si existe un hijo CORE activo, el control gateway llama `CoreCommands.cancel` con su UUID ya
  confirmado. No se solicita otro caso después del terminal cancelado.
- La intención de cancelación no es durable en este corte. Una caída antes del terminal deja una
  ejecución interrumpida que exige una nueva decisión de cancelar o reanudar.

## Consecuencias

El workspace conserva todos los intentos y el resultado científico referencia el intento que
produjo la evidencia final. No se agregan sidecars, journals desktop ni cambios a los 19 schemas,
estados o protocolo de control CORE.

