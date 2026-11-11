# ADR-0034 - Estudios comparativos de políticas de inspección

- Estado: accepted
- Fecha: 2026-08-29
- Objetivo afectado: OBJ-17
- Requisitos afectados: DE-RF-14 a DE-RF-16 y DE-RNF-08

## Contexto

`inspection-route@1.0.0` representaba un solo conjunto de visitas consecutivas.
Eso permitía contar recorridos compatibles, pero no comparar políticas bajo un
mismo catálogo de instalaciones ni distinguir una política imposible de una
ejecución fallida. La infraestructura agrupada incorporada para layouts ya
resolvía persistencia, recuperación y deduplicación, aunque sus contratos
contenían conceptos decisionales —bosques, componentes, utilidad y Pareto— que
no pertenecen al problema de inspección.

El paquete continúa en pre-release. Se admite por ello reemplazar el contrato
`1.0.0` sin migrar configuraciones ni workspaces singleton previos. La evidencia
capturada el 2026-08-24 se conserva como registro histórico de aquel contrato.

## Decisión

`inspection-route` pasa a modelar un `study` con instalaciones comunes y al
menos dos `scenarios`. Cada escenario declara su identidad, título y conjunto
no dirigido de `required_consecutive_visits`. Los pares se canonicalizan y
ordenan antes de formar identidades.

Cada escenario se valida como bosque lineal. Un ciclo o un vértice de grado
mayor que dos produce un diagnóstico de dominio con instalaciones y
obligaciones conflictivas; ese escenario no crea un `ExperimentConfig`, un
experimento ni un run CORE. La validación pura del bosque lineal se comparte
con el adaptador de layouts.

Los escenarios válidos se ejecutan bajo un UUID de dominio y un manifiesto
propio. El `constraint_set_id` es SHA-256 de `n` y las aristas canónicas; el ID
del experimento CORE es SHA-256 de la configuración CORE completa. Escenarios
con obligaciones iguales conservan resultados separados, pero reutilizan un
único experimento y run CORE.

La medida principal sigue siendo `retained-route-flexibility = C_s/U(n)`, con
`U(1)=1` y `U(n)=n!/2` para `n>=2`. No se ejecuta un baseline irrestricto. La
comparación es:

- `conclusive` si existe un escenario válido y todos los válidos tienen conteo
  seleccionable;
- `inconclusive` si algún escenario válido no tiene conteo seleccionable;
- `not_applicable` si todos los escenarios son estructuralmente inválidos.

Sólo una comparación concluyente informa todos los IDs empatados en la máxima
flexibilidad. El dominio no ordena un ranking ni recomienda una política.

La aplicación agrupada común recibe constructores y accesores del adaptador.
No contiene `forest_id`, `duplicate_forests`, `constraint_set_id` ni modelos de
ninguno de los dos dominios. `prepare` persiste únicamente la proyección;
`run` devuelve el UUID de dominio y escribe `domain_run.json`, `result.json` y
`report.md`. `resume` continúa desde cursor y casos confirmados; `render` sólo
reinterpreta evidencia existente.

## Consecuencias

- Se rebasan los seis schemas de inspección `1.0.0`, incluido su manifiesto.
- Los seis schemas de layouts y los 19 schemas públicos del CORE permanecen
  byte a byte sin cambios.
- Configuraciones y workspaces singleton de inspección deben regenerarse.
- Distancias, costos, horarios, precedencias y elección de un recorrido
  particular continúan fuera de alcance.
- La evidencia del 2026-08-29 demuestra los escenarios libre, parcial, fijado e
  inválido; la captura del 2026-08-24 no se reescribe.

## Evidencia

- `tests/domain_extensions/test_acceptance.py`
- `tests/domain_extensions/test_integration.py`
- `tests/domain_extensions/test_contracts.py`
- `traceability/domain_extensions.json`
- `docs/evidence/inspection-route/2026-08-29/`
