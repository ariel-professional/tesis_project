# Capa de adaptación de dominios

La aplicación compañera traduce configuraciones particulares al modelo formal
del CORE y vuelve a interpretar sus reportes sin incorporar vocabulario de
dominio en `tesis_proyect`.

## Recorrido

```text
DomainExperimentConfig
        |
        v
catálogo -> adaptador -> proyección inmutable
        |                       |
        |                       v
        |             domain_projections/<digest>.json
        v
generador de casos válidos -> ExperimentConfig[0..n]
        |                       |
        |                       v
        |             CoreCommands -> runs/<core_run_id>/
        v
interpretación y comparación -> domain_runs/<domain_run_id>/
```

Cada preparación crea un experimento independiente: su digest combina un nonce
aleatorio y la configuración canónica. La proyección conserva ambos y no cambia
si se edita el archivo de origen. Las proyecciones históricas sin nonce conservan
su identidad basada en configuración; no se migran al leerlas. Reanudar mantiene
el experimento existente y sus intentos. En un adaptador singleton el digest
también identifica el experimento CORE; en uno agrupado, cada caso válido tiene
una identidad aportada por el adaptador y un UUID de dominio agrupa los runs hijos.

## Frontera con el CORE

`tesis-proyect` y `tesis-domain` son adaptadores de salida hermanos. Ambos
invocan la fachada interna `CoreCommands`; ninguno ejecuta ni analiza la salida
del otro. `ExecutionObserver` distribuye notificaciones síncronas in-process:
la CLI original las adapta a NDJSON y a su terminal, mientras la CLI de dominio
las adapta únicamente a su progreso en español. No existe un broker o tópico
asíncrono.

La aplicación compañera administra `domain_projections/` y `domain_runs/` con
escrituras atómicas, paths confinados y rechazo de symlinks. La creación,
lectura y verificación de `experiments/` y `runs/` se realiza exclusivamente a
través de `CoreCommands`. La interpretación recibe el `ReportSummary` tipado que
devuelve `export`, sin releer privadamente el reporte del workspace.

La dependencia permitida desde la extensión comprende la frontera de
aplicación, contratos/modelos, errores y observación del CORE. Quedan prohibidos
los imports de su CLI, persistencia, pipeline, runner, motores y repositorios.
Esta frontera es interna a la distribución y no constituye una API Python
pública para terceros.

## Contrato del adaptador

Cada entrada del catálogo aporta conjuntamente:

- parsing estricto de la configuración;
- proyección determinista a `ExperimentConfig` y contexto reversible versionado;
- nombre descriptivo para listados;
- interpretación y renderizado del resultado.
- una medida principal explícita;
- generación perezosa y política de ejecución singleton o agrupada.

El contexto pertenece al adaptador y no presupone vértices o aristas. Un nuevo
dominio debe agregar sus modelos y schemas, mantener juntas ambas direcciones y
cambiar su versión ante cualquier modificación incompatible de la proyección.

No se descubren plugins, módulos ni código de terceros dinámicamente.

## Generación agrupada

La aplicación común conoce únicamente casos proyectados, orígenes, payloads y
accesores o constructores provistos por el adaptador. No conoce bosques,
componentes, conjuntos de obligaciones ni sus métricas concretas. Ambos
adaptadores reutilizan una validación pura de bosques lineales, pero mantienen
contratos, manifiestos, análisis y renderizadores propios.

`inspection-route` recorre los escenarios en orden declarado. Valida cada
conjunto de obligaciones antes de construir `ExperimentConfig`; ciclos y grado
mayor que dos quedan como resultados locales omitidos. Los conjuntos válidos se
deduplican por SHA-256 de `n` y aristas canónicas. Sus escenarios permanecen
separados en el resultado aunque compartan evidencia CORE. La agregación calcula
`C_s/U(n)`, el estado conservador de la comparación y todos los máximos
empatados, sin producir un ranking.

`single-row-facility-layout` deriva para cada diseño los componentes opcionales
como la diferencia entre el catálogo completo y su base. Un DFS determinista
mantiene grados, aristas y conectividad con rollback; ciclos y grado mayor que
dos podan la rama antes de invocar al CORE. Los bosques válidos se deduplican por
`forest_id`; las alternativas de decision conservan un `case_id` por diseño y
seleccion aunque compartan la misma evidencia CORE.

La enumeración puede ser exponencial porque la cantidad de salidas válidas puede
serlo. El contrato garantiza generación perezosa, poda monotónica y ausencia de
casos CORE conocidos como inválidos; no promete una complejidad asintótica
imposible.

El subconjunto vacio de cada diseño es un caso CORE ordinario y aporta `H_D`.
La agregacion deriva utilidad, disponibilidad, restrictividad y Pareto sin
recalcular conteos. Las ramas invalidas se cuentan por todos sus descendientes;
solo el modo `full` los materializa individualmente. El manifiesto confirma un
cursor y cada hijo de forma atomica para que `resume` reconstruya el generador y
continue.
