# ADR-0013 — Cross-platform local control security

- Estado: accepted


- Objetivos afectados: OBJ-0, OBJ-1, OBJ-7
- Requisitos afectados: RP-06, RP-08, RC-03, RNF-04, RNF-05
- Resuelve: BLOCK-009 y BLOCK-010
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 2 (`public_contract_catalog`), y `docs/contracts/public_contract_catalog.md`, sección 7



## Contexto

Faltaban los bytes exactos del digest, ubicación Unix y mecanismo verificable de ACL Windows.

## Alternativas consideradas

`ctypes` Win32 propio, DACL predeterminada, o `pywin32` condicional con DACL explícita.

## Decisión

Se aprueba el digest con separadores NUL, sockets Unix privados y named pipes Windows mediante `pywin32` condicional y DACL verificada del SID de logon actual.

## Justificación

La dependencia acotada reduce riesgo en APIs de seguridad Win32 y no afecta instalaciones Linux.

## Consecuencias

Una ruta Unix demasiado larga falla de forma segura. El endpoint no sustituye al lock como prueba de actividad.

## Trazabilidad

ADR-0006; catálogo público, sección 7.
