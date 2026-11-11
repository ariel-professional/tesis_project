# ADR-0033 - Utilidad, disponibilidad base y Pareto para layouts lineales

- Estado: accepted
- Objetivo afectado: OBJ-17
- Requisitos afectados: DE-RF-10 a DE-RF-13 y DE-RNF-03
- Clase de decision: `APPROVED_NOW`
- Reemplaza: la medida irrestricta y el resultado por bosque de ADR-0031; amplia
  el origen derivado de ADR-0032 sin reintroducir listas globales redundantes

## Contexto

El adaptador agrupaba selecciones que producian el mismo bosque y media cada
conteo respecto de `n!/2`. Esa evidencia era suficiente para comparar
restricciones estructurales, pero no representaba el caso de decision: cada
diseno necesita su propio baseline, una utilidad de los componentes agregados y
una frontera entre beneficio y cantidad de layouts disponibles.

La poda tambien informaba ramas rechazadas, no la cantidad real ni la causa
auditable de todas las combinaciones invalidas cubiertas por cada rama.

## Decision

Cada componente declara una utilidad entera no negativa. La configuracion
declara explicitamente si las combinaciones invalidas se reportan como resumen o
con detalle completo. Todo componente que no pertenece a la base sigue siendo
candidato del diseno.

Se separan dos identidades. `forest_id` conserva el hash de `n` y aristas, y
continua identificando el experimento y run CORE reutilizable. `case_id` es el
hash del experimento de dominio, diseno y componentes agregados; dos casos pueden
compartir bosque sin perder su utilidad ni clasificacion.

El subconjunto vacio de cada diseno aporta `H_D`. Para un caso concluyente se
calculan las fracciones exactas `H_i/H_D` y `(H_D-H_i)/H_D`. La utilidad
incremental suma solo candidatos agregados y la total incluye la base. La
dominancia y Pareto se calculan exclusivamente dentro del mismo diseno. Un
empate exacto no domina; si falta cualquier conteo del diseno, su frontera queda
inconclusa.

La poda sigue evitando casos CORE invalidos. Una rama podada cuenta todos sus
descendientes. El modo `summary` agrupa causa y conflicto sin materializarlos; el
modo `full` conserva cada combinacion cubierta y acepta explicitamente el costo
exponencial.

## Consecuencias

- Los runs CORE se siguen deduplicando por bosque y ejecutando secuencialmente.
- El resultado se agrupa por diseno y reemplaza maximos globales por invalidos,
  dominados y Pareto.
- Los porcentajes son vistas con dos decimales; JSON conserva fracciones exactas.
- `single-row-facility-layout@1.0.0` se rebasea antes del release; no existe
  migracion ni reescritura de workspaces anteriores.
- Los 19 schemas, pipeline y decisiones cientificas abiertas del CORE no cambian.

## Trazabilidad

`docs/contracts/domain_extension_contracts.md`,
`docs/architecture/domain-adaptation.md`, `traceability/domain_extensions.json`,
schemas del dominio y suite `DOMAIN-LAYOUT`.
