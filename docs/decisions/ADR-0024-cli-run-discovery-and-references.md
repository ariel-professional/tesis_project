# ADR-0024 — Descubrimiento y referencias de runs en la CLI

- Estado: accepted


- Objetivos afectados: OBJ-16
- Requisitos afectados: RC-01, RC-05 y RC-07
- Resuelve: ergonomía de selección de workspace y localización manual de runs
- Regla normativa: `docs/contracts/public_contract_catalog.md`, secciones 1 y 5



## Contexto

La gramática inicial exigía repetir `--workspace` y operar únicamente con UUID
completos. No existía una consulta para descubrir runs y copiar manualmente un
identificador largo era propenso a errores. El UUID ya es una identidad durable
adecuada, por lo que persistir aliases habría agregado estado, locking y
migraciones sin necesidad científica.

## Decisión

La CLI incorpora `list-runs` como octavo comando read-only, con salida humana
predeterminada o un `RunManifest` NDJSON por línea. Admite filtros opcionales por
experimento y prefijo, pero no por estado. Ordena por creación descendente y UUID
ascendente ante empate. Los manifests inválidos alcanzados por la consulta se
omiten con advertencias en stderr.

Los comandos que operan sobre un run aceptan el UUID canónico o un prefijo de al
menos ocho dígitos hexadecimales si es único. La resolución ocurre en la frontera
CLI y toda capa posterior recibe el UUID completo. Los prefijos de búsqueda son
case-insensitive, admiten guiones canónicos y pueden contener desde un dígito.

`--workspace` puede obtenerse de `TESIS_PROYECT_WORKSPACE`, con precedencia para
la opción explícita. `create-run --copy-run-id` copia best-effort el UUID completo
después de publicar el run; una falla de portapapeles no revierte evidencia ni
cambia el exit exitoso.

## Consecuencias

- No se persisten aliases ni índices nuevos.
- Los 19 schemas, eventos y estructura del workspace permanecen sin cambios.
- `list-runs --format ndjson` reutiliza `RunManifest` y mantiene stdout
  automatizable.
- Los mensajes humanos y advertencias siguen en stderr; la tabla humana solicitada
  explícita o implícitamente pertenece a stdout.
- Un prefijo mostrado puede volverse ambiguo en el futuro; el UUID completo nunca
  pierde validez.

## Trazabilidad

ADR-0004, ADR-0011 y ADR-0015; catálogo público, secciones 1 y 5; pruebas
`tests/cli/test_cli.py`, `tests/cli/test_output.py` y
`tests/application/test_experiments_and_sources.py`.
