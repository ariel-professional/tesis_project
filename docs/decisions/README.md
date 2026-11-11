# Registro de decisiones

Las ADR preservan contexto y consecuencias; no reemplazan las reglas operativas.
No se reescriben decisiones antiguas para acomodar el presente. Los estados del
índice son los reales, incluidas decisiones reemplazadas.

Estados: `proposed`, `accepted`, `rejected` y `superseded`. Para cambiar una ADR
aceptada se crea una nueva y se mantienen ambas.

| ADR | Estado | Decisión |
|---|---|---|
| [ADR-0001](ADR-0001-document-authority.md) | accepted | Autoridad documental original. |
| [ADR-0002](ADR-0002-json-schema-policy.md) | superseded | Política base de schemas y versiones; reemplazada por ADR-0009. |
| [ADR-0003](ADR-0003-identifiers-and-timestamps.md) | accepted | Identificadores, timestamps y enteros grandes. |
| [ADR-0004](ADR-0004-cli-contract.md) | accepted | Gramática y categorías de salida CLI. |
| [ADR-0005](ADR-0005-event-catalog.md) | accepted | Catálogo y garantías de eventos. |
| [ADR-0006](ADR-0006-local-control-protocol.md) | accepted | Protocolo local de cancelación. |
| [ADR-0007](ADR-0007-metrics-and-limits.md) | superseded | Métricas y límites base; reemplazada por ADR-0014. |
| [ADR-0008](ADR-0008-repository-governance-and-obj0.md) | accepted | Gobierno documental original y OBJ-0. |
| [ADR-0009](ADR-0009-exhaustive-configuration-and-schema-contract.md) | accepted | Configuración, fuentes, generadores y schemas exhaustivos. |
| [ADR-0010](ADR-0010-persisted-models-and-errors.md) | accepted | Modelos persistidos, resultados y errores. |
| [ADR-0011](ADR-0011-cli-events-and-inspection-output.md) | accepted | Payloads y salidas CLI. |
| [ADR-0012](ADR-0012-runner-worker-framed-protocol.md) | accepted | Protocolo runner-worker. |
| [ADR-0013](ADR-0013-cross-platform-local-control-security.md) | accepted | Control local multiplataforma. |
| [ADR-0014](ADR-0014-complete-operational-limits-and-toolchain.md) | accepted | Límites completos y toolchain. |
| [ADR-0015](ADR-0015-explanatory-human-inspection.md) | accepted | Inspección humana explicativa. |
| [ADR-0016](ADR-0016-execution-observers-and-terminal-progress.md) | accepted | Observación neutral y progreso interactivo. |
| [ADR-0017](ADR-0017-modular-monolith-boundaries.md) | accepted | Fronteras del monolito modular. |
| [ADR-0018](ADR-0018-four-functional-blocks.md) | accepted | Cuatro bloques funcionales. |
| [ADR-0019](ADR-0019-pre-release-contract-rebaseline.md) | accepted | Rebaseline pre-release `1.0.0`. |
| [ADR-0020](ADR-0020-checkpoint-reconciliation-and-recomputation.md) | accepted | Reconciliación y recomputación. |
| [ADR-0021](ADR-0021-document-consolidation-and-internal-imports.md) | accepted | Consolidación documental e imports internos no públicos. |
| [ADR-0022](ADR-0022-experiment-owned-operational-limits.md) | accepted | Los límites operativos pertenecen al experimento, sin cotas rígidas duplicadas. |
| [ADR-0023](ADR-0023-adaptive-terminal-durations.md) | accepted | Duraciones TTY adaptativas, etiquetadas y legibles. |
| [ADR-0024](ADR-0024-cli-run-discovery-and-references.md) | accepted | Descubrimiento read-only, prefijos, workspace por entorno y portapapeles explícito. |
| [ADR-0025](ADR-0025-domain-adaptation-layer.md) | superseded | Capa compañera y bundle externo; la persistencia fue reemplazada por ADR-0028. |
| [ADR-0026](ADR-0026-worker-progress-resilience-and-diagnostics.md) | accepted | Progreso factorial resiliente y diagnóstico interno acotado de workers. |
| [ADR-0027](ADR-0027-current-directory-workspace-discovery.md) | accepted | Fallback y descubrimiento superficial de workspace desde el directorio actual. |
| [ADR-0028](ADR-0028-autonomous-domain-experiments.md) | accepted | Experimentos de dominio autónomos, content-addressed y reutilizables. |
| [ADR-0029](ADR-0029-sibling-cli-adapters-over-core-commands.md) | accepted | CLI hermanas sobre una fachada interna de comandos del CORE, sin subprocess ni pub/sub. |
| [ADR-0030](ADR-0030-domain-cli-command-names-and-terminal-closures.md) | accepted | Listados concisos y cierres humanos distintos para run, resume y render. |
| [ADR-0031](ADR-0031-general-domain-adapters-measures-and-grouped-executions.md) | accepted | Adaptadores generales con medida principal y ejecuciones de dominio uno-a-muchos. |
| [ADR-0032](ADR-0032-derived-layout-components-and-domain-diagnostics.md) | accepted | Catálogo único de componentes y diagnósticos correctos para ejecuciones de dominio. |

| [ADR-0033](ADR-0033-base-relative-layout-utility-and-pareto.md) | accepted | Utilidad, disponibilidad respecto del diseno base y frontera de Pareto. |
| [ADR-0041](ADR-0041-srfl-domain-criteria-and-pareto-v2.md) | accepted | Criterios first-party, matrices completas y Pareto tipado para SRFL v2. |
| [ADR-0042](ADR-0042-srfl-desktop-version-selector.md) | accepted | Selector desktop entre las aplicaciones completas SRFL 1.0.0 y 2.0.0. |
| [ADR-0043](ADR-0043-srfl-catalog-driven-criteria-ui.md) | accepted | Catálogo Python y referencias de criterios para UI SRFL v2. |
| [ADR-0044](ADR-0044-srfl-multiple-adjacency-value-matrices.md) | accepted | Múltiples matrices cuantitativas, objetivo por matriz y compatibilidad histórica en SRFL 2.0. |
| [ADR-0045](ADR-0045-large-desktop-domain-results.md) | accepted | Resultados confirmados grandes mediante referencias verificadas sin exceder las tramas NDJSON. |
| [ADR-0046](ADR-0046-srfl-matrix-canonicalization-and-bulk-editing.md) | accepted | Canonicalización tolerante y carga masiva de matrices SRFL. |
| [ADR-0047](ADR-0047-srfl-control-designs-and-result-context.md) | accepted | Diseño de control único y antecedentes por diseño y arista en resultados SRFL 2.0. |
| [ADR-0048](ADR-0048-srfl-matrix-import-aliases.md) | accepted | Importación de matrices mediante alias. |
| [ADR-0049](ADR-0049-srfl-signed-values-and-execution-summaries.md) | accepted | Valores con signo, REL sin prioridades y resúmenes durables de ejecución SRFL 2. |
| [ADR-0050](ADR-0050-srfl-progressive-fast-plot-projection.md) | accepted | Proyección SVG progresiva y acotada de resultados SRFL de alto rendimiento; protocolo desktop `1.4`. |
| [ADR-0051](ADR-0051-independent-domain-experiments-and-run-deletion.md) | accepted | Identidad por preparación y borrado manual seguro de ejecuciones de dominio. |
| [ADR-0052](ADR-0052-srfl-derived-result-metrics.md) | accepted | Consultas derivadas paginadas sobre resultados SRFL confirmados; protocolo desktop `1.5`. |
| [ADR-0053](ADR-0053-generate-core-schemas-on-demand.md) | accepted | Generación bajo demanda de schemas CORE sin archivos generados versionados. |
| [ADR-0034](ADR-0034-comparative-inspection-route-studies.md) | accepted | Estudios comparativos de políticas de inspección con omisión local y deduplicación. |
| [ADR-0035](ADR-0035-desktop-gateway-and-domain-ui.md) | accepted | Gateway NDJSON global `1.0`, registro UI mínimo y host React nominado. |
| [ADR-0036](ADR-0036-grouped-run-attempts-and-cancellation.md) | accepted | Intentos CORE durables y cancelación cooperativa de ejecuciones agrupadas. |
| [ADR-0037](ADR-0037-grouped-run-fail-fast.md) | accepted | Detención agrupada ante el primer hijo CORE fallido. |
| [ADR-0038](ADR-0038-durable-srfl-study-description.md) | accepted | Descripción durable e identidad interna no editable para estudios SRFL. |
| [ADR-0039](ADR-0039-user-domain-templates-and-legacy-srfl-projections.md) | accepted | Plantillas de usuario durables y lectura de proyecciones SRFL anteriores a la descripción. |

Crear una ADR cuando una decisión altere contratos observables, datos persistidos,
seguridad, recuperación, compatibilidad o autoridad documental. Refactors locales
reversibles no requieren ADR.

- [ADR-0040 — Antecedentes de decisiones SRFL](ADR-0040-srfl-decision-evidence.md): accepted.
- [ADR-0053 — Exclusión durante la ejecución de dominio](ADR-0053-domain-execution-exclusion.md): accepted.
