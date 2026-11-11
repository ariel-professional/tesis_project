# ADR-0031 — Adaptadores generales, medidas y ejecuciones agrupadas

- Estado: accepted
- Objetivo afectado: OBJ-17
- Requisitos afectados: DE-RF-01 a DE-RF-13 y DE-RNF-01 a DE-RNF-07
- Clase de decisión: `APPROVED_NOW`
- Reemplaza: la relación obligatoria uno-a-uno entre experimento de dominio,
  experimento CORE y run establecida por ADR-0028

## Contexto

La primera adaptación demostró la frontera correcta con el CORE, pero sus tipos
comunes estaban ligados a `inspection-route@1.0.0` y cada experimento de dominio
producía exactamente una configuración CORE. Esa forma no permite expresar un
estudio que compare varios diseños y subconjuntos de componentes sin trasladar
vocabulario físico al CORE.

El conteo bruto tampoco basta como resultado de dominio. Su utilidad debe
expresarse mediante una medida declarada. Ejecutar como referencia un caso sin
restricciones sería especialmente costoso y duplicaría el mismo trabajo entre
dominios, aunque su cantidad se conoce de forma cerrada.

## Decisión

El catálogo sigue siendo estático y explícito. Cada adaptador declara identidad,
versión, descripción, modelos estrictos, schemas y exactamente una medida
principal. La infraestructura trata configuración, contexto y resultado como
contratos pertenecientes al adaptador; no conoce tipos de un dominio concreto.

El total de caminos físicos sin restricciones, identificando reversos, se
calcula dentro de la aplicación compañera: es `1` para `n=1` y `n!/2` para
`n>=2`. Se persiste con la representación de entero grande y las medidas son
fracciones exactas reducidas. La aplicación no crea ni ejecuta un caso CORE
irrestricto para obtener ese denominador.

Se incorpora `single-row-facility-layout@1.0.0`. Un diseño declara componentes
base presentes en todas sus combinaciones y el estudio declara componentes
variables globales. Cada componente es un camino simple no dirigido de
estaciones. La unión base más subconjunto sólo es admisible si sigue siendo un
bosque lineal.

La generación usa DFS determinista con ramas excluir/incluir. Mantiene grados,
aristas canónicas y conectividad mediante union-find con rollback. Una inclusión
que produzca grado mayor que dos o cierre un ciclo se poda antes de construir un
`ExperimentConfig`. Los componentes variables se ordenan por cantidad de
aristas descendente y luego por ID. Las bases inválidas se rechazan durante
`prepare`.

La generación es perezosa y no impone límites, truncamiento ni confirmaciones
interactivas. Informa previamente la suma teórica de `2^m` por diseño. No se
promete tiempo lineal o logarítmico: si hay exponencialmente muchas selecciones
válidas, producirlas también requiere tiempo exponencial.

Los bosques válidos se deduplican por SHA-256 de `n` y sus aristas canónicas.
Un bosque produce un único experimento y run CORE, pero conserva todos sus
orígenes. Una ejecución agrupada se identifica con UUID y confirma
atómicamente en `domain_runs/<domain_run_id>/domain_run.json` el cursor, las
métricas de generación y los IDs hijos. `resume` reconstruye el recorrido
determinista hasta el cursor y continúa; `render` sólo exporta e interpreta
runs existentes. El adaptador singleton de inspección conserva su único run y
no crea una agrupación artificial.

## Interpretación

La medida principal del nuevo dominio es la fracción de disposiciones físicas
compatibles respecto de las irrestrictas. Un `match` selecciona el conteo
coincidente; `not_applicable` con un único método exitoso lo marca como evidencia
de un solo método; un `mismatch` conserva ambos valores pero no produce una
medida concluyente.

Se resaltan todos los casos con máxima flexibilidad concluyente. Esto no los
califica como mejores layouts industriales: el dominio no modela distancia,
costo, flujo, tiempo ni seguridad. Agregar restricciones no puede aumentar la
flexibilidad, y los empates estructurales se conservan.

## Consecuencias

- Los 19 schemas y el pipeline del CORE no cambian.
- Los contratos de dominio `1.0.0` se rebasan in-place antes de release.
- Los workspaces de dominio anteriores no se migran ni se sobrescriben; deben
  regenerarse.
- Un estudio puede crear muchos experimentos y runs CORE secuenciales, pero
  `list-runs` presenta la ejecución agrupada y deja los UUID hijos auditables en
  su manifiesto y resultado.

## Trazabilidad

`docs/contracts/domain_extension_contracts.md`,
`docs/architecture/domain-adaptation.md`,
`traceability/domain_extensions.json` y suites `DOMAIN-*`.
