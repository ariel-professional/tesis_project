# Guía de adaptaciones de dominio

Esta guía describe los problemas que pueden estudiarse y cómo interpretar sus
resultados. Para instalar el proyecto y aprender a usar las referencias de las
ejecuciones, se puede consultar primero la [guía de uso](USER_GUIDE.md).

Hay dos dominios: recorridos de inspección y distribución de estaciones en una
fila. Cada uno permite describir el problema con sus propios términos, el
programa transforma esa descripción en un grafo para realizar los cálculos.

## Recorridos de inspección

`inspection-route@1.0.0` compara políticas explícitas de consecutividad sobre
las mismas instalaciones. Cada instalación se visita una vez y el recorrido
inverso se considera equivalente.

### Definir el estudio

El usuario edita un archivo con `study`, una lista común de `locations` y al
menos dos `scenarios`. Cada escenario tiene `id`, `title` y
`required_consecutive_visits`. `n`, los números de vértice y las aristas CORE no
se escriben manualmente.

Los comandos se ejecutan desde la raíz del proyecto, después de instalar las
dependencias. Un workspace es la carpeta que conserva definiciones y resultados.
Se crea una carpeta vacía `workspace` con
`New-Item -ItemType Directory workspace`; si ya existe, se puede elegir otra
carpeta o comprobar que sea el workspace deseado. La ruta indicada con `--workspace`
debe existir. La [guía de uso](USER_GUIDE.md#instalación-y-workspace) explica
la instalación.

```powershell
uv run tesis-domain prepare `
  --config examples/domains/inspection-route/comparison.json `
  --workspace workspace
```

La salida muestra un ID SHA-256 y su referencia corta. El comando guarda:

```text
workspace/
└── domain_projections/<digest>.json
```

Cada `prepare` crea un experimento independiente, aun si se repite la misma
configuración. La proyección conserva una copia autónoma de la definición;
mover o editar el archivo fuente no cambia el experimento preparado. Para
reanudar una ejecución existente se usa su referencia con `resume`.

### Listar y ejecutar

```powershell
uv run tesis-domain list-experiments --workspace workspace
uv run tesis-domain list-experiments --domain inspection-route --format ndjson --workspace workspace
uv run tesis-domain run REFERENCIA --workspace workspace
uv run tesis-domain list-runs --experiment REFERENCIA --workspace workspace
```

Se reemplaza `REFERENCIA` por la referencia de experimento que muestra `prepare`.
Tras ejecutar, `list-runs` muestra la referencia de ejecución que necesitan
`resume` y `render`.

Cada `run` crea un UUID de dominio nuevo, valida primero cada política, ejecuta
los casos CORE válidos únicos e interpreta el estudio. Los informes quedan en:

```text
workspace/domain_runs/<run_id>/
├── domain_run.json
├── result.json
└── report.md
```

Hay dos referencias distintas:

- `DOMAIN_EXPERIMENT_REF`: prefijo del digest de 64 caracteres; se usa en
  `run` y en `--experiment` de los listados;
- `RUN_REF`: prefijo de un UUID; se usa en `resume` y `render`.

`list-runs` admite además `--domain`, `--prefix` y `--format ndjson`.
Si se pasa un experimento a `resume` o `render`, el comando explica la diferencia
y muestra sus runs, pero nunca elige uno automáticamente.

### Recuperar o regenerar

```powershell
uv run tesis-domain resume RUN_REF --workspace workspace
uv run tesis-domain render RUN_REF --workspace workspace
```

`resume` repara el hijo confirmado, continúa desde el cursor del manifiesto y
luego interpreta. `render` exige un run terminal y reinterpreta exclusivamente
evidencia existente, sin crear experimentos, runs ni stages. Ambos rechazan runs
creados desde experimentos CORE ad hoc.

### Interpretar los resultados

- Una política libre tiene flexibilidad `1`; no requiere un run baseline
  adicional, porque `U(n)` se calcula directamente.
- Una cadena obligatoria reúne instalaciones que no pueden separarse.
- Una instalación libre aún puede cambiar de posición.
- Los bloques son unidades reordenables, no etapas del pipeline.
- Cada flexibilidad es la fracción exacta `C_s/U(n)`, con `U(1)=1` y
  `U(n)=n!/2` para `n>=2`.
- `comparison_status` es `conclusive` si todos los escenarios válidos tienen
  conteo seleccionable, `inconclusive` si alguno no lo tiene y `not_applicable`
  si todos son estructuralmente imposibles.
- Sólo una comparación concluyente muestra todos los escenarios empatados en la
  máxima flexibilidad; no produce ranking ni recomendación automática.
- Ciclos y grado mayor que dos se informan con sus instalaciones y obligaciones,
  pero se omiten antes del CORE y no tienen `core_run_id`.
- Escenarios distintos con obligaciones iguales permanecen separados y
  comparten un único experimento y run CORE.
- Los candidatos examinados y la duración son métricas computacionales.
- El motor exacto usa una fórmula cerrada para bosques lineales válidos. El
  motor de referencia permite contrastar resultados cuando el tamaño no supera
  el límite configurado.

El ejemplo `comparison.json` usa ocho instalaciones y reúne una política libre,
una parcial, una secuencia completamente fijada y una política imposible.

## Disposiciones de estaciones en una sola fila

`single-row-facility-layout@1.0.0` compara variantes estructurales de una fila de
estaciones modulares iguales. Una fila y su reflejo representan la misma
disposición. No modela precedencias temporales, costos, distancias, flujos ni
seguridad.

Las versiones `2.0.0` y `2.1.0` usan criterios de decisión y matrices de
relaciones; `2.1.0` ofrece además un modo de alto rendimiento. Las definiciones
y los resultados se mantienen separados por versión. La [guía desktop](DESKTOP_USER_GUIDE.md)
describe su uso.

```powershell
uv run tesis-domain prepare `
  --config examples/domains/single-row-facility-layout/comparison.json `
  --workspace workspace
uv run tesis-domain run DOMAIN_EXPERIMENT_REF --workspace workspace
```

En el ejemplo de SRFL 1.0.0, `study` declara estaciones, componentes con `utility` entera no negativa y
diseños. Cada diseño declara `base_component_ids`, los demás componentes son
candidatos.

En SRFL 2.0 puede existir un único diseño de control con base vacía. Conserva
la misma regla de generación: todos los componentes del catálogo son candidatos
y el caso sin restricciones forma parte de sus combinaciones.

La aplicación genera subconjuntos de forma perezosa. Ciclos y grado mayor que
dos podan la rama antes de crear artefactos CORE, pero todos sus descendientes
se contabilizan como combinaciones inválidas. Bosques iguales comparten un run
CORE, cada selección conserva un `case_id` distinto.

```text
workspace/domain_runs/<domain_run_id>/
├── domain_run.json
├── result.json
└── report.md
```

En el modo estándar, `resume` repara el caso interrumpido y continúa; `render`
reinterpreta los resultados existentes. El modo de alto rendimiento de SRFL
2.1.0 no admite `resume`: para repetir el cálculo se inicia otra ejecución.

En SRFL 1.0.0, el caso sin candidatos aporta `H_D`. Cada alternativa informa utilidad
incremental y total, `H_i/H_D`, restrictividad y clasificación Pareto dentro de
su diseño.

Los ejemplos `hospital-k8.json` e `industrial-k8.json` ejercitan 8 estaciones,
componentes superpuestos, conflictos y fronteras no triviales.
