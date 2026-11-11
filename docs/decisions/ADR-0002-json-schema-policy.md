# ADR-0002 — Política base de JSON Schemas y versiones

- Estado: superseded


- Objetivos afectados: OBJ-1 y todos los objetivos que persisten o consumen JSON
- Requisitos afectados: RF-01 a RF-14, RPE-01 a RPE-06, RC-07, RNF-03
- Resuelve: OPEN-JSON-SCHEMAS y `pipeline.version_value`, únicamente en las reglas aquí declaradas
- Regla normativa: `instructions.agent/increment_1_master.instructions.md`, sección 3.2

- Superseded by: ADR-0009

## Contexto

El contrato fuente enumeraba entidades y campos conocidos, pero no fijaba una versión de schema, una política de campos adicionales ni cómo representar variantes. Sin estas decisiones no era posible comenzar a versionar contratos persistidos estables.

## Alternativas consideradas

1. Usar modelos provisionales permisivos hasta avanzar con la persistencia.
2. Aceptar campos desconocidos para facilitar extensiones futuras.
3. Adoptar contratos estrictos, versionados y exhaustivos antes de implementar persistencia dependiente.

## Decisión

- `schema_version` y `pipeline_version` usan la cadena `"1.0.0"`.
- Los documentos JSON persistidos rechazan campos desconocidos.
- Las variantes usan discriminantes explícitos.
- Los JSON Schemas se versionan bajo `schemas/1.0.0/` y sus cambios se verifican mediante pruebas.
- Los campos, conjuntos `required`, nulabilidad y payloads exhaustivos deben aprobarse durante OBJ-1 antes de que un objetivo posterior dependa de ellos.

## Justificación

Los documentos persistidos constituyen una interfaz durable y serán consumidos por futuros incrementos. La validación estricta detecta incompatibilidades y evita inferir variantes a partir de campos ausentes.

## Consecuencias

- OBJ-1 debe producir schemas completos y fixtures válidos e inválidos.
- Pydantic se usa para validación externa y generación de schemas, no para lógica de dominio.
- Un cambio incompatible posterior requiere nueva versión y una decisión explícita de compatibilidad o migración.
- Esta ADR no inventa los campos exhaustivos que todavía deben cerrarse en OBJ-1.

## Trazabilidad

- `instructions.agent/increment_1_master.instructions.md`, secciones 3.2 y 5, Objetivo 1
- `docs/reference/contracts/IMPLEMENTATION_SPEC_AI.md`, `OPEN-JSON-SCHEMAS`
