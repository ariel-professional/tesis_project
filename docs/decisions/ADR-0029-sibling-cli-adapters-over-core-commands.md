# ADR-0029 — CLI hermanas sobre los comandos del CORE

- Estado: accepted
- Objetivo afectado: OBJ-17
- Requisitos afectados: DE-RF-04, DE-RF-05, DE-RF-08, DE-RF-09, DE-RNF-01,
  DE-RNF-04, DE-RNF-05 y DE-RNF-06
- Clase de decisión: `APPROVED_NOW`
- Reemplaza: integración por subprocess de ADR-0025 y la cláusula equivalente
  de ADR-0028

## Contexto

El CORE ya implementaba experimentos, ejecución, reanudación, consultas y
exportación como casos de uso de `application`. Sin embargo, `tesis-domain`
invocaba `tesis-proyect` mediante subprocess y analizaba su NDJSON. Así un
adaptador de terminal consumía accidentalmente otro adaptador de terminal: se
duplicaban mensajes como `Next command` y una referencia de experimento podía
llegar a `inspect` como si fuera un run.

`ExecutionObserver` ya es el puerto síncrono in-process que publica el avance.
`CompositeExecutionObserver` distribuye cada notificación. No existe un broker,
un tópico asíncrono ni una razón para introducirlos.

## Decisión

Se establece `CoreCommands` como fachada interna de aplicación, independiente
de Typer y de la presentación. Expone las ocho operaciones existentes:
`save_experiment`, `create_run`, `list_runs`, `run`, `resume`, `cancel`,
`inspect` y `export`; además ofrece las consultas auxiliares
`load_experiment`, resolución de referencias y referencia corta.

`tesis-proyect` y `tesis-domain` son adaptadores hermanos incluidos en la misma
distribución. Ambos invocan `CoreCommands` en el mismo proceso y componen sus
propios observers. Ninguno importa o ejecuta la otra CLI. La persistencia
opcional de eventos es una responsabilidad de la fachada de aplicación y no de
un adaptador de salida.

La CLI original conserva `PublicEventObserver` y `TerminalUiObserver`. La CLI de
dominio usa sólo `DomainTerminalObserver`, que consume las notificaciones de run
y stage sin emitir `Command`, `Status` ni próximos comandos de la presentación
original. Los resultados y próximos pasos se renderizan una sola vez al terminar
la operación.

La extensión de dominios puede depender de la frontera de aplicación, modelos,
errores y observación del CORE. No puede depender de `tesis_proyect.cli`,
persistencia, pipeline, runner, motores o repositorios internos. Sólo
`ProjectionStore` administra `domain_projections/` y `domain_runs/`; todo acceso
a `experiments/` y `runs/` pasa por `CoreCommands`.

Esta fachada es una frontera interna entre adaptadores empaquetados. No se
declara una API Python pública para terceros y no cambian la CLI, eventos,
schemas ni workspace públicos del CORE.

## Consecuencias

- se elimina el subprocess, el parsing privado de NDJSON y el acoplamiento entre
  presentaciones;
- las dos CLI comparten resolución de workspace, referencias, errores y casos de
  uso;
- `persist_events` funciona igual desde cualquiera de los adaptadores;
- una invocación de dominio puede observar progreso continuo sin contaminar su
  stdout JSON;
- `DOMAIN_EXPERIMENT_REF` y `RUN_REF` permanecen identidades diferentes y
  `list-runs` permite descubrir la relación explícitamente;
- una reorganización interna de `CoreCommands` no altera por sí misma el
  contrato público.

## Alternativas descartadas

- Mantener subprocess conservaría el defecto estructural y obligaría a seguir
  parseando la salida de otra presentación.
- Crear un broker o cola agregaría infraestructura sin asincronía entre estos
  adaptadores locales.
- Publicar una biblioteca Python estable ampliaría innecesariamente la superficie
  contractual del Incremento 1.

## Trazabilidad

ADR-0016, ADR-0017, ADR-0025, ADR-0028,
`tests/application/test_core_commands.py`, suites `DOMAIN-*` y
`traceability/domain_extensions.json`.
