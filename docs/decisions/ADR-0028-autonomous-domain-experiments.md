# ADR-0028 — Experimentos de dominio autónomos

- Estado: accepted
- Objetivo afectado: OBJ-17
- Requisitos afectados: DE-RF-01 a DE-RF-08, DE-RNF-02 y DE-RNF-04
- Clase de decisión: `APPROVED_NOW`
- Reemplaza: persistencia por bundle y vinculación uno-a-uno de ADR-0025

## Contexto

ADR-0025 separó correctamente la adaptación específica del CORE, pero expuso al
usuario un bundle externo que debía nombrar, conservar y vincular manualmente a
un único run. La configuración de dominio ya contenía toda la definición
científica y operativa, por lo que `--bundle` duplicaba una decisión de
persistencia y impedía reutilizar el experimento como hace el CORE.

La proyección debe continuar siendo auditable y reversible sin introducir datos
de dominio en los contratos del CORE ni depender del archivo editable después de
prepararlo.

## Decisión

`prepare --config FILE` crea un experimento de dominio inmutable identificado por
el SHA-256 hexadecimal de la configuración validada y canónica. El mismo digest
es un `ExperimentId` válido y nombra tanto `experiments/<digest>.json` como
`domain_projections/<digest>.json`.

La proyección contiene únicamente su identidad, creación, snapshot completo de
la configuración de dominio y un contexto reversible versionado por el
adaptador. Para `inspection-route@1.0.0` ese contexto es el mapa
instalación–vértice; las aristas y la configuración CORE se derivan y verifican,
pero no se duplican.

Los comandos posteriores resuelven prefijos del digest. `run` crea un nuevo run
CORE en cada invocación; `resume` y `render` reciben referencias de run y aceptan
sólo manifests cuyo `experiment_id` tenga una proyección válida. Los informes de
dominio se guardan por UUID bajo `domain_runs/<run_id>/`.

La aplicación compañera sigue usando la CLI para escribir `experiments/` y
`runs/`. Sólo administra directamente sus nuevos directorios reservados,
mediante escrituras atómicas, confinamiento y rechazo de symlinks.

## Consecuencias

- El usuario declara el archivo de dominio una vez y deja de administrar bundles.
- Un experimento preparado admite múltiples runs sin estado mutable compartido.
- Editar la fuente produce otro digest; los experimentos anteriores permanecen
  autónomos gracias al snapshot persistido.
- Ausencias parciales se reparan cuando la evidencia existente coincide; una
  contradicción se rechaza sin sobrescribirla.
- Los bundles pre-release no se migran ni se leen.
- Los contratos, schemas y layout reservado del CORE permanecen inalterados.

## Alternativas descartadas

- Conservar sólo la ruta fuente impediría ejecutar o interpretar después de
  moverla o editarla.
- Usar `case.id` no distinguiría configuraciones operativas diferentes.
- Persistir aristas, configuración CORE y run ID repetiría datos derivables y
  volvería a acoplar una proyección reusable con una única ejecución.

## Trazabilidad

`docs/contracts/domain_extension_contracts.md`,
`traceability/domain_extensions.json` y suites `DOMAIN-*`.
