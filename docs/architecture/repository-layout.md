# Arquitectura del repositorio

El Incremento 1 es un monolito modular. La arquitectura funcional describe el
recorrido científico; la técnica ubica responsabilidades sin exigir una carpeta
por bloque.

## Recorrido funcional

```text
configuración/fuente
        │
        ▼
materialización y validación ──► instancia canónica
        │
        ▼
análisis y conteos aislados ───► comparación
        │
        ▼
métricas y reporte derivado ───► CLI / NDJSON / JSON / Markdown

El pipeline envuelve todo el recorrido y confirma diez checkpoints durables.
```

La entrada admite inline, archivo confinado o generador reproducible. El núcleo
formal normaliza aristas, valida bosque lineal, clasifica seis casos y ejecuta
conteos. La integración persiste evidencia y reconcilia checkpoints. La salida
sólo deriva vistas desde evidencia confirmada.

## Módulos vigentes

| Área | Responsabilidad |
|---|---|
| `models` | Contratos Pydantic explícitos, enums y protocolos. No ofrece reexports generales. |
| `domain` | Hashing, validación y análisis matemático puros. |
| `engines` | Motor de referencia y adaptador exacto. |
| `persistence` | Workspace confinado, JSON atómico y repositorio run-scoped. |
| `runner` | Reloj, locks, workers y control local; protocolo común y backends Unix/Windows separados. |
| `reporting` | Construcción de `ReportSummary` y renderizado sin recomputar ciencia. |
| `pipeline` | Fuentes, coordinador, reconciliador, handlers y journal de diez stages. |
| `application` | Casos de uso y `CoreCommands`: experimentos, operaciones, inventario/inspección, exportación, referencias y selección de workspace. |
| `observation.py` | Puerto transversal y notificaciones internas neutrales. |
| `errors.py` | `OperationalError` compartido por fronteras operativas. |
| `cli` | Parsing, serialización, adaptación de eventos y presentación terminal; no contiene casos de uso. |

`stage_handlers`, `orchestrator` y `reconciliation` permanecen cohesivos: su
tamaño refleja el pipeline explícito y no justifica divisiones métricas sin una
responsabilidad nueva.

## Extensión desktop

La aplicación desktop aprobada posteriormente conserva al CORE como dependencia
y no cambia la dirección anterior:

| Área | Responsabilidad |
|---|---|
| `src/tesis_desktop_gateway/` | Adaptador NDJSON de larga vida sobre los casos de uso de dominio. |
| `desktop/src/main/` | Lifecycle Electron, validación de mensajes y proceso gateway. |
| `desktop/src/preload/` | API nominada y mínima expuesta con `contextBridge`. |
| `desktop/src/renderer/` | Shell React, host y presentación; no ejecuta ciencia. |
| `desktop/domain-ui-sdk/` | Contrato TypeScript entre shell y UI de dominio. |
| `desktop/domain-ui-kit/` | Componentes visuales, configuración declarativa y tokens oscuros compartidos. |
| `desktop_schemas/` | Contrato generado del transporte desktop. |
| `domains/*/ui/` | Módulo React first-party incluido por el registro de build. |

Cada UI de dominio mantiene `Screen` como composición y distribuye su código en
`model/` (estado y adaptadores), `config/` (defaults y definiciones), `hooks/`,
`components/`, `styles/` y pruebas. Los tipos repetidos por tres o más
consumidores se promueven al `common.types.ts` de su ámbito; el SDK no incorpora
presentación y el kit visual no conoce modelos científicos.

SRFL `2.0.0` mantiene la selección y los datos de criterios en su configuración,
pero genera snapshots first-party en la proyección. La generación nativa produce
bosques CORE y particiones de conflictos; la agregación Python deriva resultados
tipados y Pareto multidimensional. El renderer sólo selecciona ejes de una vista
1D/2D y nunca recalcula la frontera. SRFL `1.0.0` conserva su aplicación completa
de utilidad y Pareto bidimensional en un módulo UI independiente. El shell carga
uno u otro módulo por identidad versionada y muestra un loader durante el cambio;
ningún mapper convierte estudios entre versiones.

En desarrollo, Forge observa renderer, main y preload. `desktop/scripts/dev-watch.mjs`
agrega regeneración selectiva del registro/tipos, mientras main reinicia sólo el
gateway al cambiar Python. Ese ciclo no reconstruye runtime embebido, paquete o
instalador.

El asistente consulta el catálogo mediante `getLayoutDecisionCriteria()` y envía
la configuración de criterios y matrices, sin snapshots derivados. Python fija
los snapshots al preparar el experimento. Los selectores de ejes son estado
visual local y no recalculan la clasificación Pareto confirmada.

## Dirección de dependencias

```text
models
  ▲
domain     engines     errors/observation
  ▲           ▲              ▲
persistence  runner          │
  ▲           ▲              │
reporting     │              │
  ▲           │              │
pipeline ─────┴──────────────┘
  ▲
application
  ▲
cli
```

La figura es conceptual: una flecha apunta hacia una dependencia permitida. Las
reglas ejecutables son:

- modelos, dominio y motores no dependen de aplicación, pipeline, persistencia
  o CLI;
- persistencia no depende de runner, reporting, pipeline, aplicación o CLI;
- runner no depende de reporting, pipeline, aplicación o CLI;
- reporting puede leer modelos y repositorios, pero no depende del pipeline;
- pipeline no depende de aplicación ni CLI;
- aplicación coordina casos de uso y puede invocar pipeline e infraestructura;
- los adaptadores CLI componen observers y llaman a `CoreCommands`; ninguna CLI
  invoca a otra.

El motor exacto puede usar el hashing puro del dominio. Las operaciones de dominio
que preparan, coordinan o eliminan experimentos comparten el lock del workspace
con CORE para proteger la evidencia (ADR-0051). La aplicación de dominio consulta
tipos SRFL al derivar las métricas aprobadas por ADR-0052; las demás piezas de
infraestructura común no incorporan esos tipos.

`tests/architecture/test_dependencies.py` verifica dirección y ciclos sobre AST.

## Pipeline y persistencia

Los diez stages mantienen el orden contractual:

1. definición;
2. materialización del candidato;
3. validación de aristas;
4. validación de bosque lineal;
5. análisis estructural;
6. conteo exacto o skip propio;
7. conteo de referencia o skip propio;
8. comparación;
9. métricas de los últimos intentos confirmados 01–08;
10. exportación de reportes.

El orden durable es `artefactos → StageResult → pipeline.json → run.json`. El
reconciliador descubre evidencia, valida identidad e integridad, repara manifests
y recomputa desde el primer checkpoint inválido. El workspace, no los reportes,
es la autoridad.

## Interfaces observables

Son públicas la gramática CLI, eventos y payloads, schemas `1.0.0`, estructura
contractual del workspace, protocolos locales y resultados científicos. Las rutas
e imports Python internos no son API pública. La reorganización interna requiere
auditar consumidores y preservar siempre las interfaces observables.

El inventario de runs reutiliza `Workspace` y `RunRepository`, lee únicamente
manifests candidatos y resuelve referencias abreviadas en la frontera CLI. Las
capas de ejecución, control y persistencia continúan recibiendo sólo UUID
canónicos completos.

La disposición fue aceptada por ADR-0021 y verificada al cerrar OBJ-13 mediante
la prueba AST, 197 pruebas aprobadas y regeneración sin drift de los 19 schemas.
