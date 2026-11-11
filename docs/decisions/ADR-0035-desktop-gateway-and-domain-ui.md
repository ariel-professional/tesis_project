# ADR-0035 — Gateway desktop y UI por dominio

**Estado:** accepted  
**Fecha:** 2026-09-02

## Contexto

Electron necesita operaciones que la CLI no ofrece y una ejecución de larga vida. La propuesta
anterior agregaba proyectos, capabilities versionadas y varias versiones runtime que no aportan
valor al primer corte y duplican autoridad.

## Decisión

- Crear `tesis-desktop-gateway`, un proceso Python de larga vida con framing NDJSON y protocolo
  global `1.0`.
- Admitir sólo los comandos enumerados en `desktop_gateway_contracts.md`; no existe invocación
  libre, `capability_version` ni sufijo `@1`.
- Generar `desktop_schemas/1.0.0/gateway-message.schema.json` desde Pydantic y tipos TypeScript
  desde ese schema. Python y Electron main validan cada mensaje.
- Mantener el draft SRFL únicamente en memoria React hasta `study.prepare`. `prepare` reutiliza
  `ProjectionStore.prepare`; `domain_run.start` recibe sólo `domain_experiment_id`.
- Registrar una UI first-party con cuatro campos: `schema_version`, `domain_id`,
  `domain_version`, `entry`. El registro se genera con imports lazy literales y confines de path.
- Exponer un único `Screen({host})`. El host tiene métodos nominados, no versión runtime ni acceso
  genérico a IPC.
- Identificar shell, UI y gateway por la build y su hash. Sólo el protocolo de transporte tiene
  versionado independiente.

## Consecuencias

La CLI y desktop son adaptadores hermanos sobre la aplicación de dominio. El renderer no conoce
Electron, Node, paths ni `CoreCommands`. Los contratos CORE `1.0.0` permanecen intactos.

La aceptación de esta decisión no declara cerrado OBJ-17: la instalación global opcional y la
reconstrucción PDF siguen pendientes. Tampoco constituye evidencia de empaquetado Windows; esa
evidencia debe observarse antes de una release pública.

