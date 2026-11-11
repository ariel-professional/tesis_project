# Contratos de adaptación de dominios — `1.0.0`

Estos contratos pertenecen a la aplicación compañera y no amplían los 19
schemas ni el workspace reservado del CORE. El rebaseline pre-release se acepta
por ADR-0031 y su simplificación por ADR-0032: no hay migración ni reescritura
automática de workspaces de dominio anteriores.

Todos los objetos son estrictos, emiten sus propiedades declaradas, normalizan
texto semántico a Unicode NFC y usan timestamps RFC 3339 UTC con milisegundos.
Los conteos usan `LargeNonNegativeInteger`: entero hasta
`9007199254740991` y string decimal canónico para valores mayores.

## Contrato común del adaptador

Cada entrada estática del catálogo declara conjuntamente:

- `domain_id`, `version` y descripción;
- exactamente una medida principal `{id,name,definition}`;
- modelos estrictos de configuración, proyección, ejecución y resultado;
- proyección determinista a cero, uno o varios `ExperimentConfig`;
- interpretación de `ReportSummary` tipado;
- renderizado JSON, humano y Markdown.

No existe descubrimiento dinámico de plugins. La infraestructura común no
conoce configuraciones, contextos ni resultados concretos. Un cambio
incompatible exige nueva versión, salvo este rebaseline explícito anterior al
primer release.

## Identidad y proyección

Las proyecciones históricas sin `instance_nonce` mantienen su identidad SHA-256
sobre la configuración validada, en JSON compacto con claves ordenadas y UTF-8.
SRFL 1.0 también conserva la validación de sus dos formas documentales históricas.
Las nuevas preparaciones crean siempre una instancia: `instance_nonce` contiene
16 bytes aleatorios en hexadecimal minúsculo (32 caracteres), y el ID es
SHA-256 de `domain-experiment-instance-v1\0`, nonce, `\0` y la configuración
canónica UTF-8. Al leer una instancia se vuelve a validar ese cálculo. El
timestamp y los datos derivados no participan. Los comandos aceptan el ID
completo o un prefijo hexadecimal único; las operaciones requieren al menos
ocho dígitos.

Las proyecciones nuevas agregan `instance_nonce` a `schema_version`,
`domain_experiment_id`, `created_at`, el snapshot `domain_config` y el
`projection_context` del adaptador. Al leer datos antiguos, `instance_nonce` se
omite. El nombre del archivo, el campo de identidad y el cálculo del snapshot
deben coincidir. La configuración de una plantilla no contiene nonce; dos
preparaciones desde la misma plantilla crean experimentos distintos y reanudar
conserva el ID y los intentos existentes.

Un adaptador singleton puede asociar ese digest a un experimento CORE. Un
adaptador agrupado prepara sólo su proyección y crea experimentos CORE por caso
válido durante `run`. Toda lectura y escritura de `experiments/` y `runs/` pasa
por `CoreCommands`.

## Conteo irrestricto de inspección

Para `inspection-route`, con `n` vértices y recorridos inversos equivalentes,
el denominador es
`U(1)=1` y `U(n)=n!/2` para `n>=2`. Se calcula directamente en la capa de
dominio. Nunca se prepara ni ejecuta un run CORE sin restricciones para
obtenerlo. Una flexibilidad `C/U(n)` se reduce como fracción exacta.

La evidencia se interpreta así:

- `match`: se selecciona el valor coincidente;
- `not_applicable` con un único éxito: se selecciona ese valor;
- `mismatch`: se conservan ambos valores y la medida queda nula;
- sin conteo utilizable: conteo y medida quedan nulos.

## `inspection-route@1.0.0`

La configuración contiene `schema_version`, `domain`, `study` y `execution`.
`study` declara identidad, título, una lista común y ordenada de instalaciones y
al menos dos escenarios. Cada escenario contiene `id`, `title` y
`required_consecutive_visits`. Los IDs son únicos, todas las referencias deben
existir y la cantidad de instalaciones no supera `integer_limits.max_n`.

Cada obligación es una arista no dirigida: se rechazan lazos y duplicados aun
si invierten sus extremos; después se canonicaliza y ordena. La proyección
contiene sólo el snapshot y el mapa instalación–vértice. `prepare` no crea
experimentos CORE.

Durante `run`, cada escenario se valida como bosque lineal. Ciclos y grados
mayores que dos se diagnostican localmente con instalaciones y obligaciones
conflictivas, sin `core_run_id`. Los válidos producen casos agrupados. Su
`constraint_set_id` es SHA-256 de `n` y aristas canónicas; el experimento CORE
se identifica por su configuración completa. Escenarios distintos con el mismo
conjunto conservan resultados separados y comparten exactamente un run CORE.

El manifiesto usa vocabulario de inspección: escenarios de origen,
`constraint_set_id` y obligaciones. Registra UUID de dominio, cursor, métricas,
casos hijos y timestamps. `resume` continúa desde él y `render` no ejecuta
stages.

Inicio y reanudación mantienen exclusión local por run de dominio durante toda
la operación, también entre gateway y CLI. Su archivo interno `execution.lock`
bajo el directorio del run no forma parte de la evidencia científica ni altera
los schemas. Los runs históricos sin archivo se leen sin migración. Sólo un
bloqueo ocupado demuestra actividad; `running` con bloqueo adquirible permite
recuperar una interrupción. Se conservan identidad, cursor confirmado e historial.
El resultado se publica antes de confirmar el manifiesto completado. Véase ADR-0053.

Su medida principal es `retained-route-flexibility`: `C_s/U(n)`. El resultado
conserva cada escenario en orden declarado y define `comparison_status` como
`conclusive`, `inconclusive` o `not_applicable`. Sólo el primer estado emite
todos los `most_flexible_scenario_ids` empatados. No ordena un ranking ni
recomienda una política. Cada ejecución escribe `domain_run.json`, `result.json`
y `report.md` bajo el UUID de dominio.

## `single-row-facility-layout@1.0.0`

La configuración contiene `schema_version`, `domain`, `study`, `execution` y
`reporting`. Este ultimo exige `invalid_combinations:"summary"|"full"`.
`study` contiene identidad interna, título, descripción opcional, estaciones, un catálogo de
componentes y diseños. La descripción se conserva en la proyección y el resultado confirmado.

ADR-0040 extiende el contrato pre-release `1.0.0`: `study.attachments`, y `description` más
`attachments` en componentes y diseños. Las listas tienen default vacío y las descripciones
default nulo. `Attachment` es una unión estricta por `kind`:

- `file`: `sha256` hexadecimal minúsculo, `name`, `media_type` PNG/JPEG/WebP/PDF y
  `size_bytes` entero no negativo.
- `link`: `url` HTTP/HTTPS completa sin espacios y `label` opcional/nulo.

Los metadatos documentales participan del hash de configuración; los bytes se conservan
separadamente bajo `domain_attachments/<sha256>`. No cambian la generación ni las medidas
científicas. La consulta Desktop deriva del snapshot de la proyección, sin duplicación por caso.
Las dos formas históricas previas, con y sin `study.description`, conservan su identidad
solo cuando los nuevos campos documentales están vacíos. No se reescriben proyecciones antiguas.

Un componente es un camino de al menos dos estaciones distintas. El inverso es
equivalente y no puede duplicar otro componente. Cada componente declara
`utility`, un entero no negativo sin maximo oculto. Un diseño declara uno o mas
componentes base, presentes en cada combinación. Para ese diseño, todo componente
del catálogo que no esté en la base es opcional; el subconjunto vacío genera la
base. La suma teórica es `Σ 2^(|componentes|−|base del diseño|)`.

La unión admite aristas compartidas, pero no ciclos ni grado mayor que dos. Las
bases se validan en `prepare`. La generación DFS excluir/incluir mantiene
grados, aristas y union-find con rollback; una inclusión inválida poda toda su
rama antes de construir un caso CORE. El orden es determinista: más aristas
primero y luego ID.

Cada bosque se identifica por `forest_id`, SHA-256 de `n` y las aristas
canónicas, y comparte un experimento y run CORE. Cada alternativa de decision
conserva un `case_id` distinto, derivado del experimento de dominio, el diseño
y los componentes agregados, aunque reutilice el mismo bosque.

`domain_runs/<domain_run_id>/domain_run.json` confirma UUID, experimento de
dominio, estado, cursor, métricas, casos, orígenes, IDs CORE y timestamps. Los
runs hijos se ejecutan secuencialmente. `resume` repara un hijo registrado y
continúa desde el cursor; `render` no crea experimentos ni runs ni ejecuta
stages.

Su medida principal es `base-relative-layout-availability`: `H_i/H_D`,
donde el subconjunto vacío del diseño aporta `H_D`. Cada componente declara
utilidad entera no negativa; el resultado informa utilidad incremental y total,
disponibilidad, restrictividad y Pareto por diseño. Si falta cualquier conteo del
diseño, sus ratios y frontera quedan inconclusos.

Las ramas podadas contabilizan todos sus descendientes. `summary` agrupa causas
y conflictos; `full` conserva además cada combinación inválida.

## Borrado manual de una ejecución

Desde una tarjeta de «Ejecuciones», eliminar el experimento elimina esa
ejecución de dominio y sus intentos CORE, experimentos CORE, adjuntos y
proyección sólo cuando son exclusivos. Se reúnen los `core_run_id` de todos los
intentos, no sólo el último. Si otra ejecución conserva una referencia CORE o
de dominio, sus datos permanecen. Las proyecciones históricas compartidas se
conservan mientras otra ejecución las apunte. Una plantilla guarda su propia
configuración y permanece en `domain_templates/`; por eso no obliga a conservar
la proyección. Los adjuntos permanecen si otra proyección o plantilla los cita.

El borrado se rechaza ante una operación científica activa, un lock CORE activo,
una referencia necesaria que no pueda validarse, una ruta no canónica o un
symlink en el árbol afectado. Antes de borrar se guarda un inventario interno
con destinos e identidades. La recuperación sólo continúa ese inventario; si un
destino cambió o dejó de ser seguro, se detiene. No se agregan limpieza
automática, borrado masivo ni migración de workspaces; `OPEN-RETENTION` permanece
sin resolver.

## Resúmenes y schemas

Los listados conservan identidades, referencias cortas, dominio, nombre, estado
y timestamps. Para ejecuciones agrupadas, el run listado es el UUID del
manifiesto de dominio; los UUID CORE hijos quedan en manifiesto y resultado.

Los schemas exhaustivos están en:

- `domain_schemas/inspection-route/1.0.0/`;
- `domain_schemas/single-row-facility-layout/1.0.0/` (histórico congelado);
- `domain_schemas/single-row-facility-layout/2.0.0/`.

## `single-row-facility-layout@2.0.0`

Version 2 is a separate contract for new studies. Components do not contain
`utility`; criteria are selected in `decision_model` and at least one first-party
criterion is required. REL and flow matrices are complete and preserve explicit
zeros. Results use separate typed fields for retained layouts, each non-empty
REL `A/E/I/O` level, captured flow and warning findings. They contain no generic
`value`, `score` or `utility`. Objective snapshots are generated by Python and
persisted in the projection during `prepare`.

Un estudio puede declarar como máximo un diseño de control con
`base_component_ids: []`. Los demás diseños deben tener una base no vacía. El
control conserva la generación normal: todos los componentes del catálogo son
opcionales, genera `2^|C|` selecciones e incluye el bosque vacío.

REL `U` and `X` are explicit inputs but never Pareto dimensions. Every `X` has
exactly one explicit policy and no non-`X` pair may have one. Directed flow sums
both directions for every prescribed canonical pair; symmetric flow uses one
canonical entry. Decimal quantities and exact fractions are never converted to
binary floating point. Pareto classification is typed, exact and conservative;
its result records dimensions, dominators and exact differences.

Every selected REL criterion must declare at least one `A/E/I/O` relation, and
each resulting REL level must intersect at least one component edge. A selected
flow criterion must intersect at least one component edge whose declared flow is
positive. These checks reject objectives that are structurally constant at zero;
the desktop editor exposes matching REL pairs as candidate restrictions instead
of silently turning the whole matrix into an exponential candidate set.

Undesired adjacencies declare cause, explanation, provenance and exactly one
`forbidden|warn` policy. Base prohibitions reject `prepare`; optional
prohibitions prune branches and are recorded. Warnings do not alter feasibility
or Pareto. Version `1.0.0` remains readable as historical data and is never
rewritten automatically.

ADR-0044 amplía `adjacency_flow` como una unión compatible. El objeto histórico
se conserva sin cambios; los experimentos nuevos pueden declarar una lista no
vacía de matrices cuantitativas. Cada matriz aporta una dimensión Pareto propia,
con alias, unidad, fuente y dirección `maximize|minimize`, y produce una
observación tipada en `adjacency_values`. No existe suma global ni ponderación
entre matrices. Los IDs dinámicos usan `adjacency-<matrix-id>`.

ADR-0046 hace tolerante la entrada de matrices no dirigidas: los extremos de cada
par se ordenan antes de validar unicidad y completitud. Un par repetido en sentidos
opuestos sigue siendo un duplicado inválido. Esta normalización no afecta matrices
dirigidas ni modifica la forma JSON persistida.

ADR-0047 mantiene los antecedentes fuera del resultado repetido por caso. Desktop
los recupera desde la proyección inmutable mediante `study.documentation` y los
relaciona en memoria con el diseño, las restricciones y las aristas visibles.

### Consultas derivadas de métricas

ADR-0052 agrega consultas de sólo lectura sobre resultados SRFL 2.0/2.1
confirmados. `domain_run.metrics` pagina hasta 50 filas y devuelve un resumen
compacto; diseño, criterio y caso se validan contra el resultado. El análisis
conserva valores exactos y no vuelve a ejecutar CORE ni modifica el resultado
persistido. En alto rendimiento, los casos se leen desde artefactos verificados.
