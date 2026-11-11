# ADR-0030 — Nombres de comandos y cierres de la CLI de dominio

- Estado: accepted
- Objetivo afectado: OBJ-17
- Clase de decisión: `APPROVED_NOW`

## Contexto

Los nombres `list-domain-experiments` y `list-domain-runs` repetían el contexto
que ya expresa `tesis-domain`. Además, los cierres humanos de `run`, `resume` y
`render` no distinguían correctamente si todavía existía una acción útil.

## Decisión

Los comandos públicos son `list-experiments` y `list-runs`; los nombres
anteriores se rechazan y no se mantienen aliases ocultos. `run`, `resume` y
`render` conservan cierres humanos diferentes. `render` es terminal: regenera
la interpretación desde evidencia existente, no ejecuta stages y no propone
otro `render`.

Si `resume` o `render` reciben una referencia de experimento en lugar de una
referencia de run, diagnostican la confusión, muestran los runs relacionados y
proponen la sintaxis específica del comando solicitado. Nunca seleccionan el
run más reciente de forma implícita.

## Consecuencias

- La gramática es más corta sin perder precisión entre experimentos y runs.
- Los scripts que usaban los nombres pre-release deben actualizarse.
- Los filtros y payloads de listado permanecen sin cambios.

## Trazabilidad

`tests/domain_extensions/test_cli.py` y
`docs/evidence/domain-cli-naming-verification-2026-08-25.md`.
