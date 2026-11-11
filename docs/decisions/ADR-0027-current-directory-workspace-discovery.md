# ADR-0027 — Descubrimiento superficial de workspace desde el directorio actual

- Estado: accepted
- Objetivo afectado: OBJ-17
- Decisiones extendidas: ADR-0004 y ADR-0024
- Clase de decisión: `APPROVED_NOW`

## Contexto

La CLI exigía seleccionar siempre una raíz durable mediante `--workspace` o
`TESIS_PROYECT_WORKSPACE`. Esa explicitud favorece scripts reproducibles, pero
resulta innecesariamente ceremoniosa cuando una persona invoca la herramienta
desde la carpeta que contiene su workspace.

No existe un archivo marcador. Por lo tanto, cualquier descubrimiento sólo puede
afirmar compatibilidad estructural, no propiedad semántica de una carpeta.

## Decisión

`--workspace` pasa a ser opcional. La precedencia es opción explícita, variable
`TESIS_PROYECT_WORKSPACE` y, por último, descubrimiento desde `Path.cwd()`.
Argumentos o variables inválidos fallan y nunca activan el fallback.

Un directorio es estructuralmente compatible cuando contiene `experiments/` y
`runs/` como directorios reales. El fallback usa `.` si ya es compatible; de lo
contrario inspecciona únicamente sus subdirectorios inmediatos y esos dos hijos
esperados. No lee archivos, no recorre niveles adicionales y no busca en padres.

- Un candidato se usa directamente.
- Varios candidatos producen exit 64, una lista determinista y requieren
  `--workspace`.
- Una carpeta actual vacía se inicializa como workspace.
- Una carpeta ocupada sin candidatos reutiliza o crea
  `tesis_workspace[_n]`, eligiendo primero un workspace válido, luego una
  candidata vacía y finalmente el menor nombre libre.
- Una subcarpeta inaccesible se omite con advertencia en stderr.
- La inicialización crea `experiments/` y `runs/`, incluso para `list-runs`;
  ese comando no crea ni modifica experimentos o runs.

Las rutas de `--workspace` conservan semántica nativa: una ruta relativa se
resuelve contra el directorio actual y una absoluta se reconoce por su formato.
No se agregan `-a`, estado global ni comando `use`.

`tesis-domain run` y `render` aplican la misma política. La aplicación compañera
mantiene una implementación propia y probada por conformidad para no importar
internos de `tesis_proyect`; su gateway siempre entrega al CORE la ruta absoluta.

## Consecuencias

- La invocación habitual puede omitir el workspace sin perder confinamiento.
- La detección puede producir falsos positivos si otra carpeta usa casualmente
  ambos nombres; la ambigüedad nunca se resuelve arbitrariamente.
- La primera consulta en una ubicación sin workspace puede inicializar el
  contenedor durable.
- No cambian schemas, stages, modelos científicos, bundles ni layout interno.
- Los comandos sugeridos continúan incluyendo la ruta absoluta para ser
  reproducibles fuera de la terminal original.

## Trazabilidad

OBJ-17; RC-01, RC-05 y RC-07; DE-RF-04 y DE-RF-08; pruebas de selección de
workspace, CLI CORE y CLI de dominios.
