# ADR-0004 — Gramática y categorías de salida de la CLI

- Estado: accepted


- Objetivos afectados: OBJ-1 y OBJ-8
- Requisitos afectados: RC-01 a RC-07, RF-01, RF-02 y RF-13
- Resuelve: OPEN-CLI-SYNTAX y el mapeo general de exit codes
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 3.3



## Contexto

El contrato fuente fijaba siete comandos y sus responsabilidades, pero no la posición de argumentos, el workspace obligatorio, el uso de stdin ni el formato seleccionable de inspección.

## Alternativas consideradas

1. Comandos que descubrieran el workspace implícitamente y aceptaran configuración por stdin.
2. Una CLI flexible con múltiples sintaxis equivalentes.
3. Una gramática única con workspace explícito y servicios internos separados del parser.

## Decisión

Se adopta la gramática exacta declarada en la sección 3.3 del master para `save-experiment`, `create-run`, `run`, `resume`, `cancel`, `inspect` y `export`.

`--workspace` es global y obligatorio. No se aceptan comandos ni configuraciones por stdin en la primera versión. `inspect` admite `human` y `ndjson`. Los servicios permanecen desacoplados de Typer.

El ejecutable inicial es `tesis-proyect` y `python -m tesis_proyect` ofrece la misma CLI. El éxito usa 0 y los fallos se agrupan en las categorías numéricas 64, 65, 66, 69, 70, 74, 75 y 78 definidas en el master.

## Justificación

Una única gramática disminuye ambigüedad para scripts y futuros consumidores. Exigir el workspace evita depender del directorio actual. Separar parser y servicios conserva el core reutilizable.

## Consecuencias

- La ayuda de Typer no define lógica de negocio.
- `stdout` y `stderr` deben respetar el contrato de eventos y diagnósticos.
- Los códigos de dominio viajan en el error estructurado y no reemplazan automáticamente el exit code general.
- Un cambio futuro de la gramática pública requiere una nueva ADR.

## Trazabilidad

- `instructions.agent/increment_1_master.instructions.md`, sección 3.3
- `docs/reference/contracts/IMPLEMENTATION_SPEC_AI.md`, `OPEN-CLI-SYNTAX`
