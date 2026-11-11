# ADR-0025 — Capa de adaptación de dominios

- Estado: accepted
- Objetivo afectado: OBJ-17
- Requisitos afectados: DE-RF-01 a DE-RF-08, DE-RNF-01 a DE-RNF-05
- Clase de decisión: `APPROVED_NOW`

## Contexto

El Incremento 1 entrega un CORE reproducible para instancias de caminos
hamiltonianos con aristas prescritas. La devolución académica posterior solicita
demostrar cómo un usuario formula un problema particular, lo proyecta al modelo
formal y recupera conclusiones expresadas nuevamente en su dominio.

ADR-0018 ya distingue los bloques funcionales de entrada, modelo formal,
integración y salida, pero declara futuras las extensiones específicas. La nueva
capacidad debe materializar esos extremos sin modificar los contratos públicos
`1.0.0` ni introducir conceptos particulares dentro del CORE.

## Decisión

Se incorpora un paquete compañero, `tesis_domain_extensions`, con una CLI
independiente, `tesis-domain`. El paquete usa exclusivamente la CLI y los
artefactos públicos de `tesis_proyect`; no importa módulos Python internos ni
escribe directamente el workspace del CORE.

Los dominios disponibles se enumeran en un catálogo explícito incluido en la
distribución. Cada entrada ofrece conjuntamente dos operaciones versionadas:
proyectar una configuración de dominio a `ExperimentConfig 1.0.0` e interpretar
un `ReportSummary` confirmado en términos del problema original. No se admiten
plugins dinámicos, imports configurables ni ejecución de código proporcionado
por usuarios.

La primera entrada es `inspection-route@1.0.0`. Modela instalaciones como
vértices y obligaciones de visita consecutiva como aristas prescritas. Sus tres
contratos viven en `domain_schemas/inspection-route/1.0.0` y no forman parte de
los 19 schemas del CORE.

## Consecuencias

- `ExperimentConfig`, `ReportSummary`, eventos, CLI, stages, hashes y workspace
  del CORE permanecen inalterados.
- La única entrada editable por caso es `DomainExperimentConfig`; configuración
  canónica, mapa reversible e informes son evidencia derivada.
- Un bundle externo al workspace vincula la configuración con el experimento y
  el run sin agregar metadatos al CORE.
- La integración por subprocess conserva la frontera pública a costa de un
  proceso adicional y del análisis estricto de NDJSON.
- Esta capacidad es posterior al cierre original del Incremento 1 y no cambia el
  estado bloqueado de OBJ-9.

## Alternativas descartadas

- Un adaptador aislado por dominio reduce infraestructura, pero no demuestra un
  mecanismo reutilizable.
- Plugins descubiertos dinámicamente agregan compatibilidad, confianza y
  seguridad innecesarias para la entrega actual.
- Agregar datos de dominio a `ExperimentConfig` rompería el contrato estricto
  `1.0.0` y contaminaría el CORE.

## Trazabilidad

Devolución académica recibida después de la demostración del Incremento 1;
ADR-0017, ADR-0018 y `traceability/domain_extensions.json`.
