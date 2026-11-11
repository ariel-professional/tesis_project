# Guía de usuario — aplicación desktop

La aplicación desktop permite configurar y ejecutar estudios de disposición de
instalaciones en una sola fila sin usar la CLI. Incluye las aplicaciones
completas `single-row-facility-layout@1.0.0`, basada en utilidad, y
`single-row-facility-layout@2.0.0` y `2.1.0`, basadas en criterios de decisión,
matrices REL o cuantitativas y Pareto multidimensional.

## Abrir la aplicación

Si se dispone de un `Setup.exe` de la misma versión, se instala la aplicación y
se abre desde el menú Inicio. Si sólo se dispone del código, se puede seguir el apartado de desarrollo de
la [guía de instalación](DESKTOP_INSTALLATION_AND_UPDATE.md#preparar-el-entorno-de-desarrollo).
El instalador contiene Electron, la UI y el runtime Python necesarios; no requiere
una instalación separada de Python o Node.

Este prototipo no está firmado. Windows puede mostrar SmartScreen: antes de
continuar, se debe verificar que el SHA-256 del instalador coincida con
`desktop/release-evidence/SHA256SUMS.json` entregado junto al artefacto.

## Elegir aplicación y modelo

En la barra superior, el selector **Aplicación / modelo** permite cambiar entre:

- **SRFL 1.0.0:** editor completo de utilidades, ejecución y resultados Pareto
  bidimensionales originales;
- **SRFL 2.0.0:** editor completo de criterios, REL, matrices cuantitativas, políticas `X` y
  Pareto multidimensional;
- **SRFL 2.1.0:** los mismos criterios con ejecución estándar o de alto
  rendimiento y consultas paginadas para resultados grandes.

Al cambiar de versión aparece un indicador de carga mientras se abre la
aplicación correspondiente. Cada versión muestra sus propias plantillas,
ejecuciones y definiciones.
No se convierten estudios entre versiones: un JSON debe abrirse desde la
aplicación que coincide con `domain.version`.

La selección inicial es `2.1.0` cuando está disponible; de lo contrario se
selecciona la primera aplicación disponible. La identidad activa aparece en Inicio,
en el asistente y al pie de la barra lateral. Cambiar de versión descarta un
borrador todavía no preparado; las ejecuciones y demás evidencia durable del
workspace no se modifican.

## Crear un estudio

La pantalla inicial permite **Empezar desde cero**, **Usar plantilla**, abrir un
archivo JSON o pegar una definición existente. Una plantilla es una configuración
guardada que puede servir de punto de partida para otro estudio. Una definición
importada se valida y luego se muestra en formularios; no es necesario editar JSON.

Para una primera exploración, se puede elegir **Usar plantilla**, seleccionar
una de la versión activa y recorrer sus datos hasta **Revisión**. Allí se pueden
comprobar las restricciones y la cantidad estimada de combinaciones antes de seleccionar
**Preparar y ejecutar**. El cálculo guarda un experimento y abre su progreso;
al terminar, la pantalla permite consultar los resultados por diseño.

El asistente recorre información general, criterios, estaciones, datos de
relaciones, adyacencias, diseños, configuración avanzada y revisión. En
**Criterios** se elige una o más dimensiones: disposiciones compatibles
retenidas, prioridades de cercanía o valores de adyacencias obligatorias. Cada tarjeta informa
dirección, unidad, fórmula, evidencia y limitaciones.

En **Datos de relaciones**, una relación REL registra la prioridad de cercanía
entre dos estaciones. Se declaran todos los pares no ordenados y se registra el
nivel `A/E/I/O/U/X`, razón y procedencia. Cada relación `X` necesita una política
explícita de advertencia o prohibición, con causa, explicación y procedencia. El
usuario puede seleccionar varias celdas REL y aplicarles en conjunto nivel, motivo
y fuente. También puede copiar equivalencias numéricas por nivel REL a una matriz
cuantitativa elegida; es una carga explícita y no una sincronización permanente.
Cada matriz cuantitativa exige todas las celdas aplicables —incluidos ceros—, además de
nombre, explicación, objetivo maximizar/minimizar, unidad, período opcional,
fuente y la elección dirigida/no dirigida. Se pueden agregar, duplicar o eliminar
matrices sin un máximo oculto. Las matrices pueden completarse en tabla o
importarse como CSV mediante los alias de estación que muestra el paso
**Estaciones**. El ID y el alias son de solo lectura; el alias es una ayuda visual
y no reemplaza al ID científico.

REL admite dos formatos. La lista usa el encabezado obligatorio
`alias_1;alias_2;nivel_rel;motivo_operativo;fuente`, permite actualizaciones
parciales y deja motivo y fuente vacíos si todavía no se conocen. La matriz usa
los alias en la primera fila y la primera columna, puede ser completa o triangular
y conserva los motivos y fuentes ya cargados. Las matrices cuantitativas se
importan completas con el mismo encabezado matricial: si ambos sentidos coinciden
se configuran como no dirigidas; si difieren, se configuran como dirigidas. El
botón de información del importador ofrece ejemplos listos para copiar con los
alias reales del experimento.

La última importación matricial fija el orden visual común de REL y de todas las
matrices cuantitativas. Las relaciones y los valores continúan asociados a los
identificadores de estación, por lo que reordenar la vista no reasigna datos.
Cada sección también permite alternar entre la matriz y una lista. Al agregar,
renombrar o eliminar estaciones se conservan los valores todavía aplicables;
un doble clic abre la edición individual de una celda cuantitativa.

**Procedencia** es la fuente que permite rastrear el dato: por ejemplo, una
medición, una norma, un documento de trabajo o el juicio de
una persona experta. No describe el valor ni su motivo; esos datos se registran
en los campos correspondientes.

En **Restricciones candidatas**, cada prioridad REL muestra el motivo operativo,
el flujo asociado y si ya puede participar en las alternativas. Una prioridad se
convierte en restricción con un clic; también pueden construirse pares o caminos
ordenados desde el diagrama. La vista previa del camino muestra su efecto REL y
de flujo antes de agregarlo. Debe existir al menos una candidata por cada nivel
REL prioritario utilizado (`A/E/I/O`). Las matrices cuantitativas admiten valores
positivos, nulos y negativos según lo que representan. En **Diseños** se eligen las restricciones que
serán obligatorias; las restantes se comparan como alternativas opcionales.
Una restricción y su recorrido inverso representan el mismo camino: si ya
existe, el asistente no la duplica y muestra una notificación temporal.

En **Información general** se define un título y, opcionalmente, una descripción
que se conserva en la proyección y en el resultado. El identificador científico
se genera internamente y no se edita desde los formularios.

La configuración avanzada muestra el nombre técnico real y una explicación en
español para cada opción. En **Revisión**, la aplicación valida el estudio y el
bosque, estima las combinaciones y habilita **Preparar y ejecutar**. El switch
**Guardar como plantilla** conserva esa configuración para iniciar estudios futuros.

El borrador existe sólo en memoria. Cerrar o recargar la aplicación antes de
**Preparar y ejecutar** descarta esos cambios. Al ejecutar con el switch activo,
la configuración también queda guardada como plantilla. La estimación no persiste
el borrador.

Las plantillas incluidas con la aplicación son de sólo lectura. Las plantillas
creadas por el usuario viven en el workspace y aparecen junto a ellas en Inicio.
Desde el detalle o resultado de una ejecución también se puede activar o desactivar
**Guardar como plantilla** sin modificar ni borrar la ejecución original.

## Progreso y cancelación

Durante la ejecución el editor se bloquea y muestra el progreso y el estado
terminal. En el modo estándar, los casos CORE válidos se ejecutan
secuencialmente. El modo de alto rendimiento de SRFL 2.1 usa un procesamiento
propio para conjuntos grandes y presenta sus resultados mediante consultas paginadas.

**Cancelar** solicita la cancelación cooperativa. Si un caso CORE está activo,
también se cancela ese hijo y no se genera otro caso. La confirmación puede tardar
hasta que se detenga el cálculo en curso y se confirme la cancelación.

Una ejecución cancelada conserva su evidencia y sus intentos anteriores. Al usar
**Reanudar** en modo estándar, los casos completados se reutilizan y un hijo
CORE cancelado recibe un intento nuevo. Las ejecuciones de alto rendimiento de
SRFL 2.1 no se pueden reanudar: para volver a calcular hay que iniciar una nueva.

## Recuperar una ejecución interrumpida

Si Electron o el gateway terminan antes de confirmar el estado terminal de una
ejecución estándar, al abrir la aplicación se muestra el run SRFL no completado
más reciente. Es necesario elegir:

- **Cancelar**, para confirmar su terminación sin continuar la generación; o
- **Reanudar**, para comprobar los resultados guardados y continuar desde el
  último progreso confirmado, reutilizando los casos ya completados.

Después de una caída puede ser necesario volver a indicar si se desea cancelar
o reanudar la ejecución estándar.
Una ejecución de alto rendimiento interrumpida no se reanuda; debe iniciarse una nueva.

## Leer los resultados

Al completar, la pantalla separa los resultados por diseño. Para cada diseño
muestra la clasificación Pareto calculada con todas las dimensiones activas y
una tabla de casos. En alto rendimiento, los resultados grandes se consultan por
páginas. El explorador usa una vista de una dimensión cuando hay un solo criterio
y permite elegir dos ejes distintos cuando hay varios.
Primero aparece el resumen de casos no dominados a ancho completo y luego una
vista previa del gráfico. Su botón de expansión abre un explorador de pantalla
completa con grilla y leyenda. Cada eje permite elegir una transformación automática,
lineal, de raíz cuadrada, logarítmica ajustada o por percentiles. La transformación
logarítmica permite configurar su parámetro `k`. Los controles están disponibles en
la vista previa y en el explorador expandido, y permanecen sincronizados. Los ejes
reflejan el rango de los valores representados, que no necesariamente empieza
en cero. El gráfico se ajusta al visor y los ejes y las tablas muestran el nombre
legible de cada criterio.
El criterio **Cobertura de prioridades de cercanía** indica qué porcentaje de las
relaciones prioritarias de cada nivel REL fue incorporado por la alternativa como
adyacencia obligatoria; no representa una propiedad teórica ni una distancia física.

Los identificadores no se imprimen sobre los puntos: el detalle aparece al
seleccionarlos. Los ejes X e Y representan criterios distintos. Los
cuadrados indican casos no dominados y los círculos, casos dominados. La línea
del frente une únicamente puntos ya clasificados como no dominados por Python.
Debajo se pueden consultar los casos válidos y ordenarlos mediante los
encabezados disponibles. Cambiar ejes u
orden no recalcula la frontera global. El icono del ojo abre un detalle legible
con el bosque de restricciones y adyacencias. Si diferentes selecciones de
componentes producen exactamente el mismo bosque, el gráfico y las tablas lo
muestran una sola vez como alternativa física; el detalle conserva la lista de
selecciones equivalentes.

Según los criterios elegidos, cada caso informa:

- fracción exacta de disposiciones compatibles retenidas;
- cumplimiento REL por nivel `A/E/I/O`, excluyendo `U` y `X` del cociente;
- una dimensión por matriz cuantitativa, con alias, objetivo, unidad, período y contribuciones;
- estado no dominado o dominado, dominadores y diferencias por dimensión;
- advertencias derivadas de políticas `X` sin alterar factibilidad ni Pareto.

La aplicación `1.0.0` muestra utilidad y Pareto bidimensional según su contrato;
las aplicaciones `2.0.0` y `2.1.0` muestran sus criterios tipados. Los
resultados nunca mezclan dimensiones de versiones distintas.

La referencia del caso, el run CORE, el bosque de restricciones y otros datos
técnicos están disponibles en **Ver detalle del caso**.

La frontera nunca mezcla casos de diseños distintos. Los reportes y resultados
se derivan de la evidencia confirmada del workspace; no se recalculan en React.

## Documentar decisiones

La información del estudio, el detalle desplegable de cada restricción y la
justificación de cada diseño permiten escribir texto y agregar antecedentes.
En **Imagen / Plano / PDF** se pueden arrastrar o seleccionar varios archivos;
se admiten PNG, JPEG, WebP y PDF. En **URL / Link** se pueden agregar enlaces
HTTP/HTTPS con etiqueta opcional. Los enlaces se abren mediante una acción
explícita en el navegador del sistema.

**Ver adjunto** abre un visor independiente con zoom y ajuste al ancho; los PDF
permiten cambiar de página sin descargar el archivo entero. Escape cierra el
visor y devuelve el foco al botón de origen. Los archivos se copian al workspace:
una vez guardados, no dependen de su ubicación original.

Al abrir una plantilla, **Importar adjuntos** e **Importar descripción/detalle de
las restricciones** comienzan desactivados. El primero controla archivos y enlaces
heredados de los tres niveles; el segundo controla únicamente los textos de las
restricciones. Las descripciones del estudio y los diseños se heredan siempre.
Cambiar los switches conserva las modificaciones propias y no recupera adjuntos
eliminados individualmente.

La revisión reúne la documentación antes de preparar. Los resultados permiten
consultarla sin editar; el detalle de un caso muestra el diseño y las restricciones
utilizadas. En SRFL 2.0, se puede seleccionar una arista del diagrama para consultar su nivel
REL, motivo operativo, fuente, política, valores cuantitativos y antecedentes.
Una carga pendiente impide avanzar. Si un JSON referencia un archivo ausente,
se debe adjuntar el mismo contenido o quitar la referencia antes de preparar.

Quitar un adjunto elimina su asociación, no las copias confirmadas que pueden
estar utilizadas por otros experimentos. Al respaldar el workspace debe incluirse `domain_attachments`.
La CLI todavía no ofrece este editor ni el visor documental.

## Datos locales y respaldo

En Windows, la build actual guarda el workspace dentro del directorio `userData`
de Electron, normalmente:

```text
%APPDATA%\tesis-proyect-desktop\workspace
```

Allí viven proyecciones, plantillas del usuario, runs de dominio y runs CORE. Para
obtener un respaldo consistente, se debe cerrar la aplicación antes de copiar el
workspace. No se deben editar sus archivos JSON ni eliminar runs hijos manualmente:
el workspace es la autoridad científica.

No hay limpieza automática, sincronización remota, proyectos editables ni
recuperación del borrador previo a **Preparar y ejecutar**.

## Problemas frecuentes

| Síntoma | Acción |
|---|---|
| No aparece ningún dominio | Reinstale una build completa; el registro UI y el catálogo Python no coinciden. |
| No aparece el selector **Aplicación / modelo** | Comprobar que está abierta la versión actual. En desarrollo, cerrar las instancias anteriores y ejecutar `npm run dev` desde `desktop/`; modificar el repositorio no actualiza una instalación existente. |
| Un JSON no abre en la versión activa | Seleccionar la versión indicada por `domain.version`; no existe conversión automática. |
| Una ejecución estándar reaparece como interrumpida | Elegir explícitamente cancelar o reanudar. En alto rendimiento debe iniciarse una ejecución nueva. |
| La cancelación no es instantánea | Esperar a que el cálculo en curso confirme la cancelación. |
| Un resultado dice `inconcluso` | Preservar el workspace; falta evidencia científica confirmada para ese caso. |
| La aplicación no inicia | Verificar el hash y la arquitectura Windows x64; en una build de desarrollo, consultar el log de la terminal. |

La instalación y las actualizaciones se describen en
[DESKTOP_INSTALLATION_AND_UPDATE.md](DESKTOP_INSTALLATION_AND_UPDATE.md).
