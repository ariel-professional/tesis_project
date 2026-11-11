# ADR-0032 — Componentes derivados y diagnósticos de dominio

- Estado: accepted
- Objetivo afectado: OBJ-17
- Requisitos afectados: DE-RF-09 a DE-RF-13 y DE-RNF-03
- Clase de decisión: `APPROVED_NOW`
- Reemplaza: la declaración de componentes variables globales y el origen
  `selected_variable_component_ids` establecidos por ADR-0031

## Contexto

`single-row-facility-layout` declaraba todos los componentes en un catálogo y
exigía repetir en `variable_component_ids` cuáles podían agregarse a una base.
La distinción no respondía a un caso de uso vigente: obligaba a clasificar dos
veces la misma información y permitía configuraciones redundantes.

La revisión de `tesis-domain` también detectó descripciones singleton en la
ayuda, errores de configuración sin ubicación ni causa y un diagnóstico que
omitía ejecuciones agrupadas al recibir una referencia de experimento.

## Decisión

`components` es el catálogo completo del estudio. Para cada diseño, los
componentes opcionales son exactamente los IDs del catálogo que no pertenecen a
`base_component_ids`. Por lo tanto, el diseño con base `B` sobre un catálogo `C`
declara `2^|C-B|` combinaciones teóricas. La generación, poda y deduplicación
conservan las reglas de ADR-0031.

Los orígenes persistidos usan `{design_id,added_component_ids}`. El segundo campo
contiene sólo los componentes agregados a la base que produjeron ese bosque.

La CLI describe todas las operaciones como ejecuciones de dominio. Los errores
de configuración identifican la ruta y causa de cada problema. Cuando `resume`
o `render` reciben una referencia de experimento, el diagnóstico consulta tanto
runs singleton como ejecuciones agrupadas.

## Consecuencias

- `variable_component_ids` deja de pertenecer a la configuración y proyección;
- no existe filtrado adicional por diseño: todo componente no base es opcional;
- los contratos de dominio `1.0.0` se rebasan in-place antes del release;
- configuraciones, proyecciones, manifiestos y resultados anteriores no se
  migran ni reescriben;
- el CORE, sus 19 schemas y su pipeline permanecen sin cambios.

## Trazabilidad

`docs/contracts/domain_extension_contracts.md`,
`docs/architecture/domain-adaptation.md`, `traceability/domain_extensions.json`,
suites `DOMAIN-CLI` y `DOMAIN-LAYOUT`.
