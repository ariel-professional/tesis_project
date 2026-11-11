# Guía de uso — CORE y adaptación de dominios

Esta guía explica cómo ejecutar un primer experimento desde una terminal en
Windows. El proyecto ofrece dos interfaces de línea de comandos:

- `tesis-proyect` opera el CORE con vértices y aristas prescritas;
- `tesis-domain` permite declarar un caso con vocabulario de dominio y traduce
  tanto la configuración como el resultado.

Ambas interfaces reciben órdenes escritas en una terminal y utilizan el mismo
núcleo de cálculo.

La interfaz gráfica se documenta por separado en
[DESKTOP_USER_GUIDE.md](DESKTOP_USER_GUIDE.md). Su instalación y actualización
están en [DESKTOP_INSTALLATION_AND_UPDATE.md](DESKTOP_INSTALLATION_AND_UPDATE.md).

## Instalación y workspace

En Windows, se debe abrir PowerShell en la carpeta raíz del proyecto, que contiene
`pyproject.toml`. La [guía de instalación](DESKTOP_INSTALLATION_AND_UPDATE.md#preparar-el-entorno-de-desarrollo)
explica cómo comprobar e instalar Python y `uv`. Después se ejecuta:

```powershell
uv sync --frozen --extra dev
uv run tesis-proyect --help
uv run tesis-domain --help
```

El *workspace* es la carpeta donde se guardan configuraciones, ejecuciones y
resultados. Puede indicarse con `--workspace`, mediante
`TESIS_PROYECT_WORKSPACE` o por el descubrimiento desde el directorio actual.
La opción explícita tiene precedencia. Un workspace contiene como mínimo
`experiments/` y `runs/`; si el directorio actual está vacío, se inicializa allí.
La ruta que se indica explícitamente debe existir. Para crear una carpeta nueva
para los ejemplos siguientes, se ejecuta una sola vez `New-Item -ItemType Directory workspace`.
Si ya existe, se puede usar otra carpeta vacía o comprobar que sea el workspace deseado.

## Uso directo del CORE

Esta interfaz se utiliza cuando el problema ya está expresado como un grafo de `n`
vértices y un conjunto de aristas obligatorias.

El ejemplo siguiente guarda una configuración y crea una ejecución. Estas
órdenes se ejecutan desde la raíz del proyecto:

```powershell
uv run tesis-proyect --workspace workspace save-experiment `
  --id demo --config examples/core-basico.json
uv run tesis-proyect --workspace workspace create-run --experiment demo
uv run tesis-proyect --workspace workspace list-runs
```

La referencia de la nueva ejecución aparece en la salida de `create-run` o
`list-runs`. En las órdenes siguientes se sustituye `RUN_REF` por esa referencia:

```powershell
uv run tesis-proyect --workspace workspace run RUN_REF
uv run tesis-proyect --workspace workspace inspect RUN_REF
uv run tesis-proyect --workspace workspace export RUN_REF
```

El ejemplo `examples/core-basico.json` define cuatro vértices y la arista
obligatoria `[1, 2]`. Los reportes quedan en `workspace/runs/<UUID>/reports/`.

La configuración `ExperimentConfig` declara `schema_version`, `n`, `source`,
`methods`, los trece `integer_limits`, `persistence` y
`counting_convention`. Las fuentes admitidas son `inline`, `file` confinado al
workspace y `generator` reproducible. Los contratos exhaustivos están en
`docs/contracts/public_contract_catalog.md`.

Los comandos del CORE son:

| Comando | Argumentos principales | Efecto |
|---|---|---|
| `save-experiment` | `--id ID --config FILE` | Valida y guarda un experimento inmutable. |
| `create-run` | `--experiment ID [--copy-run-id]` | Crea un run nuevo. |
| `list-runs` | `[--experiment ID] [--prefix PREFIX] [--format human\|ndjson]` | Lista runs válidos sin mutar. |
| `run` | `RUN_REF` | Ejecuta un run creado. |
| `resume` | `RUN_REF` | Reconcilia y continúa un run. |
| `cancel` | `RUN_REF` | Solicita cancelación idempotente. |
| `inspect` | `RUN_REF [--stage STAGE] [--format human\|ndjson]` | Consulta evidencia sin mutar. |
| `export` | `RUN_REF` | Regenera reportes de un run terminal. |

`RUN_REF` puede ser el UUID completo o un prefijo hexadecimal único de al menos
ocho caracteres. Para resolver ambigüedades se utiliza `list-runs --prefix`.

## Uso mediante un dominio

Una configuración de dominio describe el problema con sus propios términos.
Por ejemplo, el estudio de inspección identifica instalaciones y relaciones de
consecutividad. El programa traduce esos datos al grafo y luego interpreta el
resultado. La [guía de dominios](DOMAIN_GUIDE.md) explica los modelos disponibles.

El flujo es:

```text
domain_config.json
       │ prepare
       ├──> domain_projections/<digest>.json
       └──> experiments/<digest>.json (sólo adaptador singleton)
                    │ run
                    ├──> experiments/<case_digest>.json (casos agrupados)
                    ├──> runs/<core_run_id>/...
                    └──> domain_runs/<domain_run_id>/...
```

### 1. Crear la configuración

La distribución incluye `inspection-route@1.0.0` y las versiones `1.0.0`,
`2.0.0` y `2.1.0` de `single-row-facility-layout`. El primero compara políticas de visitas
consecutivas sobre instalaciones comunes; el segundo compara combinaciones de
componentes para una fila de estaciones. En ambos, el orden inverso es
equivalente y cada adaptador declara una medida principal.

Para este primer recorrido se utilizará directamente el ejemplo de inspección
incluido en el proyecto. Para modificarlo, se puede abrir y crear una copia.
El ejemplo de distribución de estaciones utiliza la versión SRFL 1.0.0:

```text
examples/domains/inspection-route/comparison.json
examples/domains/single-row-facility-layout/industrial-k8.json
```

La configuración del ejemplo SRFL 1.0.0 contiene `schema_version`, `domain`, `study`,
`execution` y `reporting`. Cada componente lineal declara una `utility` entera
no negativa. La política obligatoria
`reporting.invalid_combinations` acepta `summary` o `full`: el primer modo
agrupa conflictos y el segundo conserva también cada combinación inválida.

En este dominio, cada diseño se evalúa contra su propio caso base. El resultado
conserva las fracciones exactas `H_i/H_D` y `1-H_i/H_D`, informa utilidad
incremental y total, y separa casos dominados de la frontera de Pareto. Bosques
iguales reutilizan un run CORE mediante `forest_id`, pero cada selección mantiene
su identidad decisional `case_id`. Los ejemplos `hospital-k8.json` e
`industrial-k8.json` muestran fronteras no triviales con ocho estaciones.

El estudio de inspección contiene exactamente `schema_version`, `domain`,
`study` y `execution`. En `study.locations`, el orden determina el mapeo
reversible a vértices. Cada elemento de `study.scenarios` declara identidad,
título y `required_consecutive_visits` mediante IDs de instalaciones. El
ejemplo de ocho instalaciones incluye políticas libre, parcial, fijada e
imposible.

Los pares de cada política son no dirigidos, se canonicalizan y no admiten
lazos ni duplicados inversos. Durante `run`, ciclos y grado mayor que dos se
diagnostican y omiten antes del CORE. Las políticas válidas informan la fracción
exacta `C_s/U(n)`; el resultado conserva el orden declarado, muestra todos los
empates de máxima flexibilidad sólo si la comparación es concluyente y nunca
recomienda una política automáticamente. Políticas distintas con las mismas
obligaciones comparten un run CORE, pero conservan resultados independientes.

### 2. Preparar el experimento de dominio

```powershell
uv run tesis-domain prepare `
  --config examples/domains/inspection-route/comparison.json `
  --workspace workspace
```

`prepare` valida y normaliza la configuración, crea una identidad nueva para el
experimento y guarda su proyección. El ID es un SHA-256 calculado a partir de la
configuración canónica y un identificador aleatorio propio de la preparación.
Para un adaptador singleton también nombra el experimento CORE; para los dos
estudios agrupados los experimentos CORE se crean después, uno por caso válido
único. En inspección, `prepare` persiste sólo la proyección.
La salida distingue:

```text
ID del experimento: 927975444f32...7dc6dd4
Referencia del experimento: 92797544
Próximo comando:
  tesis-domain run 92797544 --workspace ".../workspace"
```

Cada `prepare`, incluso con la misma configuración, crea un experimento distinto.
Después se puede mover o eliminar el archivo fuente: la proyección conserva una
copia autónoma de la configuración. Para recuperar una ejecución existente se usa
su referencia con `resume`, sin volver a preparar el experimento.

La referencia mostrada arriba es ilustrativa. Debe copiarse la que devuelve la
preparación realizada, pues identifica el experimento que se ejecutará.

### 3. Listar y ejecutar

```powershell
uv run tesis-domain list-experiments --workspace workspace
uv run tesis-domain run DOMAIN_EXPERIMENT_REF --workspace workspace
```

Se reemplaza `DOMAIN_EXPERIMENT_REF` por la referencia de `prepare`. Cada `run`
crea una ejecución ligada al experimento preparado y exporta e
interpreta los `ReportSummary` del CORE. Ambos dominios crean un UUID de dominio
que agrupa sus UUID CORE hijos:

```text
workspace/domain_runs/<run_id>/
├── domain_run.json
├── result.json
└── report.md
```

En una terminal interactiva, `tesis-domain` presenta un único progreso
transitorio en español, incluido el avance continuo de los stages de conteo. No
muestra `Command`, `Status` ni `Next command` de la CLI original. Con
`--format json`, stdout contiene sólo el resultado JSON del adaptador; el
progreso no TTY no produce salida.

### 4. Distinguir experimentos de runs

Las referencias no son intercambiables:

| Referencia | Identidad completa | Se usa en |
|---|---|---|
| `DOMAIN_EXPERIMENT_REF` | digest SHA-256 de 64 caracteres | `run`, `list-experiments`, `list-runs --experiment` |
| `RUN_REF` | UUID v4 CORE o UUID de ejecución de dominio | `resume`, `render`, `list-runs --prefix` |

Para descubrir ejecuciones:

```powershell
uv run tesis-domain list-runs --workspace workspace
uv run tesis-domain list-runs `
  --experiment DOMAIN_EXPERIMENT_REF `
  --domain inspection-route `
  --format ndjson `
  --workspace workspace
```

Si se pasa por error una referencia de experimento a `resume` o `render`, la CLI
lo explica, lista sus runs asociados y muestra el comando de consulta. Nunca
selecciona implícitamente el run más reciente.

### 5. Reanudar o regenerar

```powershell
uv run tesis-domain resume RUN_REF --workspace workspace
uv run tesis-domain render RUN_REF --workspace workspace
```

`resume` usa la reconciliación del CORE y luego vuelve a exportar e interpretar.
En una ejecución agrupada repara primero el hijo confirmado, reconstruye el
generador hasta su cursor y continúa secuencialmente.
Las ejecuciones SRFL 2.1 de alto rendimiento no admiten `resume`; para repetir
el cálculo se inicia una ejecución nueva con el experimento preparado.
`render` exige un run terminal y sólo regenera la exportación y los archivos de
`domain_runs`; no ejecuta stages ni modifica el pipeline. Ambos rechazan runs de
experimentos CORE ad hoc que no tengan una proyección de dominio válida.

En salida humana, `resume` se identifica como reanudación y ofrece `render` como
posible paso posterior. `render` se identifica como regeneración del informe y
termina allí: no imprime un “Próximo comando” autorreferencial.

Los comandos de dominio son:

| Comando | Argumentos principales | Efecto |
|---|---|---|
| `list-domains` | `[--format human\|json]` | Lista adaptadores incluidos. |
| `prepare` | `--config FILE [--workspace PATH] [--format human\|json]` | Crea un experimento independiente y su proyección. |
| `list-experiments` | `[--domain ID] [--prefix PREFIX] [--workspace PATH] [--format human\|ndjson]` | Lista experimentos de dominio válidos. |
| `list-runs` | `[--experiment DOMAIN_EXPERIMENT_REF] [--domain ID] [--prefix RUN_PREFIX] [--workspace PATH] [--format human\|ndjson]` | Lista ejecuciones singleton o agrupadas válidas. |
| `run` | `DOMAIN_EXPERIMENT_REF [--workspace PATH] [--format human\|json]` | Crea, ejecuta e interpreta una ejecución nueva. |
| `resume` | `RUN_REF [--workspace PATH] [--format human\|json]` | Reanuda e interpreta una ejecución. |
| `render` | `RUN_REF [--workspace PATH] [--format human\|json]` | Regenera sus reportes sin ejecutar stages. |

## Layout del workspace

```text
workspace/
├── experiments/
│   └── <domain_experiment_id>.json
├── domain_projections/
│   └── <domain_experiment_id>.json
├── runs/
│   └── <run_id>/
│       ├── config/
│       ├── run.json
│       ├── pipeline.json
│       ├── stages/
│       ├── artifacts/
│       ├── reports/
│       │   ├── result.json
│       │   └── report.md
│       └── logs/
│           ├── runner.log
│           └── events.ndjson (si persist_events=true)
└── domain_runs/
    └── <run_id>/
        ├── domain_run.json
        ├── result.json
        └── report.md
```

La proyección nueva contiene `schema_version`, `domain_experiment_id`,
`instance_nonce`, `created_at`, la configuración `domain_config` y `projection_context`. Para
`inspection-route`, el contexto contiene su versión y `vertex_mapping`; no
duplica aristas, configuración CORE, experiment ID ni run ID.

## Salidas, estados y recuperación

`tesis-proyect` conserva su contrato público: eventos NDJSON por stdout y salida
humana de terminal por stderr TTY. `tesis-domain` tiene presentación propia y no
serializa esos eventos en stdout. La copia durable en `logs/events.ndjson`
depende sólo de `persistence.persist_events` y funciona desde ambas CLI.

Un run pasa por `created`, `running` y un estado terminal `completed`, `failed` o
`cancelled`. El workspace y sus checkpoints son la autoridad; los reportes son
derivados.

| Síntoma | Acción |
|---|---|
| referencia de experimento usada en `resume/render` | Ejecutar el `list-runs --experiment ...` sugerido y elegir un `RUN_REF`. |
| referencia de run ambigua | Agregar caracteres o usar `list-runs --prefix`. |
| experimento CORE ad hoc rechazado | Usar `tesis-domain prepare` para crear una proyección válida. |
| proyección o experimento no coinciden | Preservar la evidencia y no sobrescribir archivos manualmente. |
| `RUN_ALREADY_ACTIVE` | No ejecutar `run/resume` en paralelo; usar `cancel` desde el CORE si corresponde. |
| `INTEGRITY_ERROR` | No editar artefactos durables; inspeccionar y conservar el workspace para diagnóstico. |
| método exacto no disponible | El motor exacto usa la fórmula cerrada para bosques lineales válidos; el método de referencia puede omitirse por su límite configurable. |

No existe un limpiador automático. Respaldar y eliminar evidencia es una
decisión manual de retención.

La explicación del dominio está en `docs/DOMAIN_GUIDE.md`; sus contratos y
schemas se encuentran en `docs/contracts/domain_extension_contracts.md` y en
los subdirectorios versionados de `domain_schemas/`.
