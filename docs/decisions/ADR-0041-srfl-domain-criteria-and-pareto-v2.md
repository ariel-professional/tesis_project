# ADR-0041 — Criterios de decisión y Pareto para SRFL v2

- Estado: accepted
- Objetivo: OBJ-17
- Reemplaza para `single-row-facility-layout@2.0.0`: ADR-0033
- Compatibilidad: `1.0.0` permanece histórica y no se reinterpreta

## Decisión

La versión `2.0.0` elimina `utility`, `total_utility` y la clasificación Pareto
bidimensional de los estudios editables nuevos. El catálogo first-party ofrece
`retained-compatible-layouts@1`, `rel-closeness-{a|e|i|o}@1` y
`captured-adjacency-flow@1`. Cada observación conserva estado, dirección, unidad,
desglose y limitaciones; no existe un valor genérico.

REL y flujo son matrices completas. REL registra cada par no ordenado con nivel
`A/E/I/O/U/X`, razón y procedencia. Flujo registra todos los pares no reflexivos,
incluyendo ceros explícitos, con unidad, horizonte y dirección. Los datos
incompletos impiden `prepare`.

Cada `X` requiere exactamente una política `forbidden` o `warn`. Una prohibición
en la base rechaza el diseño; una prohibición opcional poda la rama y conserva la
causa en la partición de combinaciones. `warn` sólo produce un hallazgo y no
altera factibilidad ni Pareto.

Los casos v2 se generan con el bosque lineal nativo y pueden compartir sólo la
proyección CORE necesaria para ejecutar el conteo; no se transforman a una
configuración de dominio v1 ni se inyectan utilidades cero. La frontera Pareto se
calcula en Python, dentro de cada diseño, con fracciones exactas y todas las
dimensiones activas. Empates no dominan. Si falta una dimensión concluyente en
cualquier caso factible, la frontera del diseño es `inconclusive`.

Una dimensión seleccionada debe poder aportar información a la comparación. REL
requiere al menos una relación `A/E/I/O` y, para cada nivel activo, al menos una
de sus relaciones debe aparecer en una restricción candidata. Flujo requiere al
menos una restricción candidata con movimientos positivos. La UI permite crear
esas candidatas directamente desde REL y anticipa su efecto REL/flujo, sin
convertir automáticamente toda la matriz en componentes ni multiplicar el espacio
de búsqueda sin decisión del usuario. En resultados, selecciones de componentes
que producen el mismo `forest_id` se consolidan visualmente como una alternativa
física y sus orígenes equivalentes permanecen disponibles en el detalle.

Las comprobaciones de accionabilidad se aplican a configuraciones nuevas. Las
proyecciones `2.0.0` ya persistidas conservan lectura de solo lectura: se siguen
verificando su contrato e integridad, pero no se invalidan retroactivamente por
una regla de autoría incorporada después de su creación.

El gateway runtime usa protocolo `1.1`, conserva el schema `1.0` como histórico
y expone `layout.decision_criteria` junto con el método nominado
`getLayoutDecisionCriteria()`. La UI first-party se registra como
`single-row-facility-layout@2.0.0`; los artefactos v1 sólo se consultan en modo
histórico y de solo lectura.

## Exclusiones

Esta decisión no incorpora 3D, distancia física, funciones personalizadas,
penalizaciones graduadas, fórmula analítica de conteo ni migración automática de
workspaces v1.
