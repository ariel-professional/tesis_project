# ADR-0018 — Cuatro bloques funcionales del sistema

- Estado: accepted


- Objetivos afectados: OBJ-10
- Requisitos afectados: RNF-01, RP-01, RP-05, RPE-06, RC-01 a RC-07
- Resuelve: no aplica
- Regla normativa: `instructions.agent/objectives/OBJ-10_technical_simplification.instructions.md`



## Contexto

ADR-0017 define fronteras técnicas del monolito modular, pero esas fronteras
no expresan por sí solas la arquitectura funcional de alto nivel. Presentar
`cli`, `application`, `pipeline`, `models` o `persistence` como bloques del
producto confunde organización del código con capacidades del sistema.

## Alternativas consideradas

Se consideró hacer coincidir cada bloque funcional con un paquete Python,
mantener únicamente el mapa técnico de ADR-0017 o documentar ambos niveles y
su relación muchos-a-muchos.

## Decisión

La arquitectura funcional se organiza en cuatro bloques relacionados:

1. **Entrada, adaptación y generación**: interfaces de uso específicas de un
   dominio, extensiones, adaptadores que producen la forma canónica y
   generadores sistemáticos de instancias.
2. **Modelo formal**: núcleo matemático-formal y motores que implementan las
   formulaciones para efectuar el conteo.
3. **Integración, validaciones y corrección**: pipeline de validación y
   registro durable de la experimentación. Este bloque coordina el tránsito
   entre entrada, modelo formal y salida.
4. **Salida**: adaptadores que presentan el resultado y, cuando exista una
   extensión de dominio, lo reconvierten a los términos del problema inicial.

Los paquetes Python son unidades técnicas subordinadas a estos bloques. No se
exige ni se desea una correspondencia uno-a-uno entre bloque y directorio.
Modelos, persistencia, runner y observación son capacidades transversales.

El Incremento 1 implementa una entrada y una salida canónicas genéricas. Un
mecanismo público de extensiones de dominio y la reconversión específica de
salida son capacidades futuras; esta decisión no inventa sus protocolos ni
amplía los contratos vigentes. La formulación exacta general continúa
`UNRESOLVED`.

## Justificación

Separar arquitectura funcional y arquitectura técnica permite razonar primero
sobre el recorrido del problema y después sobre los módulos que lo realizan.
También evita presentar infraestructura operativa como una capacidad de
negocio y deja visibles las extensiones aún no implementadas.

## Consecuencias

- ADR-0017 continúa gobernando las dependencias internas del monolito.
- La documentación arquitectónica debe mostrar ambos niveles y su mapeo.
- Un módulo técnico puede colaborar con más de un bloque funcional.
- No se declaran implementados puertos de extensión o adaptadores de dominio
  que todavía no existen.
- No cambian schemas, CLI, eventos, workspace, stages ni protocolos.

## Trazabilidad

Arquitectura de alto nivel confirmada por el responsable del proyecto el
2026-08-10; ADR-0017; OBJ-10; contrato operativo del Incremento 1.
