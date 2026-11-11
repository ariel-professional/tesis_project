# ADR-0014 — Complete operational limits and toolchain

- Estado: accepted


- Objetivos afectados: OBJ-0, OBJ-1, OBJ-5, OBJ-7, OBJ-9
- Requisitos afectados: RF-10, RF-12, RP-06, RPE-08, RNF-04
- Resuelve: catálogo final de límites de OPEN-DEFAULT-LIMITS
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, secciones 2 y 3.6, y `docs/contracts/public_contract_catalog.md`, sección 2.4
- Supersede: ADR-0007


## Contexto

Los diez límites iniciales no acotaban mensajes worker ni rotación del log.

## Alternativas consideradas

Límites privados, tamaño ilimitado, o campos públicos obligatorios y reproducibles.

## Decisión

Se conservan las métricas de ADR-0007 y se adopta el catálogo de trece límites del contrato público. Se adopta uv con lock, Hatchling, Python `>=3.12`, Pydantic `>=2.13,<3`, Typer `>=0.27,<1` y pywin32 solo en Windows.

## Justificación

Los límites públicos permiten reproducir runs y defender todas las fronteras de memoria/disco. El lock hace reproducible el entorno.

## Consecuencias

No existe límite superior declarado de Python; el soporte efectivo depende de CI. Los valores basales no son defaults.

## Trazabilidad

ADR-0007; catálogo público, sección 2.4; plan aprobado.
