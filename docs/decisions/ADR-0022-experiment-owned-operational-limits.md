# ADR-0022 — Límites operativos definidos por el experimento

- Estado: accepted


- Objetivos afectados: OBJ-14
- Requisitos afectados: RF-10, RF-12, RP-06, RPE-08, RNF-04
- Resuelve: corrección de los rangos rígidos de `IntegerLimits`
- Regla normativa: `docs/contracts/public_contract_catalog.md`, sección 2.4
- Supersede: ADR-0014 únicamente respecto de cotas rígidas para límites configurables


## Contexto

La configuración del experimento contiene trece límites operativos obligatorios,
pero los modelos imponían además máximos globales y mínimos arbitrarios. En
particular, `reference_max_n` no podía superar 20 aunque ese campo existe
precisamente para que cada experimento decida hasta dónde intentar el motor de
referencia. Esta duplicación rechazaba decisiones explícitas antes de ejecutar.

## Alternativas consideradas

1. Elevar algunos techos conservando límites universales.
2. Mantener techos privados fuera del schema.
3. Hacer que los valores persistidos del experimento sean la única política y
   validar sólo tipo y signo necesarios para interpretar cada campo.

## Decisión

- Los trece campos de `IntegerLimits` siguen siendo enteros obligatorios.
- Se eliminan todos los máximos rígidos.
- Los tamaños y tiempos deben ser positivos; `max_n` y `reference_max_n` también.
- `cancellation_grace_ms` y `runner_log_backup_count` pueden ser cero; los demás
  campos no.
- `WorkerLimits` conserva exactamente las mismas restricciones estructurales para
  los valores derivados de la configuración.
- Timeouts, cancelación y framing aplican los valores elegidos; no existe un
  segundo umbral silencioso.
- El contrato `1.0.0` se amplía en el lugar: todo documento antes válido continúa
  válido y sólo se aceptan valores que anteriormente se rechazaban.

## Justificación

La reproducibilidad exige persistir la política efectiva del run. Un techo oculto
o duplicado hace que el valor configurado no sea la autoridad y obliga a cambiar
el programa para explorar rangos nuevos.

## Consecuencias

El usuario puede elegir valores costosos o imprácticos. Esa decisión queda
limitada por los timeouts y la cancelación configurados, y puede consumir recursos
significativos. Valores demasiado pequeños para contener un mensaje fallarán en
la frontera correspondiente de forma explícita.

## Trazabilidad

OBJ-14; modelos de configuración y worker; schemas `experiment-config` y
`worker-request`; pruebas contractuales de valores grandes y mínimos.
