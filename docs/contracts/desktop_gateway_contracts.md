# Contrato desktop — protocolo global `1.5`

**Estado:** approved  
**Decisiones:** ADR-0035, ADR-0036, ADR-0044, ADR-0050, ADR-0051

El transporte es NDJSON UTF-8, un objeto por LF, con máximo de 32 MiB por mensaje. Todo mensaje
incluye `protocol_version: "1.5"` y se valida contra
`desktop_schemas/1.5.0/gateway-message.schema.json`.

`domain_run.result` devuelve el resultado inline cuando la respuesta completa cabe en una trama.
Para resultados mayores, el gateway devuelve internamente a Electron main una referencia acotada
al `result.json` confirmado, con UUID de ejecución, tamaño y SHA-256. Main sólo resuelve la ruta fija
del run dentro del workspace, rechaza symlinks y escapes, y verifica tamaño e integridad antes de
parsear. Si una recarga de desarrollo deja momentáneamente Electron main en una build anterior, el
host del renderer resuelve la referencia mediante bloques de `attachments.read` autorizados sólo
para ese resultado y también verifica el SHA-256 completo. La UI de dominio recibe en ambos casos
el mismo objeto de resultado. Este mecanismo no aumenta el límite por trama ni autoriza lectura
genérica del workspace.

Los comandos permitidos son: `hello`, `ping`, `shutdown`, `domains.list`, `layout.decision_criteria`, `templates.list`,
`templates.load`, `templates.save`, `templates.set_for_run`, `study.validate`, `study.prepare`, `layout.validate_forest`,
`layout.estimate_combinations`, `domain_run.start`, `domain_run.cancel`, `domain_run.resume`,
`domain_run.status`, `domain_run.list`, `domain_run.delete`, `domain_run.result`, `domain_run.case_page`,
`domain_run.case_detail`, `domain_run.dominators`, `domain_run.frontier` y
`domain_run.plot_points`, `domain_run.plot_projection` y `domain_run.metrics`. Las consultas indexadas requieren un resultado confirmado del modo
`high_performance`. Las páginas y bloques llevan como máximo 50 elementos; los cursores son
posiciones dentro del run identificado en cada solicitud.

`domain_run.delete` recibe `{domain_run_id}` con UUID v4 completo y devuelve
`{deleted_domain_run_id, deleted_domain_experiment, preserved_template}`. Elimina la ejecución
seleccionada y únicamente sus datos exclusivos. Conserva proyecciones y artefactos compartidos.
`deleted_domain_experiment` identifica la proyección que se eliminó o es `null` si otra ejecución
la referencia; `preserved_template` indica si se conservó la plantilla correspondiente.

`domain_run.plot_projection` recibe el run, diseño, objetivos, escalas y parámetros,
nivel `0..2`, sección (`groups` o `frontier_positions`) y cursor. Cada respuesta
contiene hasta 50 elementos. La primera página calcula y retiene en memoria del proceso
una sola proyección acotada por combinación de run/diseño/ejes/escalas; páginas y niveles
reutilizan ese resultado. Cambiar cualquiera de esos parámetros reemplaza la entrada.
La frontera se pagina aparte y conserva una posición por cada caso no dominado; las
agrupaciones incluyen cantidad, centro transformado y rangos originales de ambos ejes.
La operación no cambia el resultado SRFL persistido ni reemplaza `plot_points`.

`domain_run.metrics` recibe `domain_run_id`, `metric_id`, `design_id` opcional,
`criterion_id`/`case_id` según la métrica y un cursor. Sólo lee resultados SRFL 2.0/2.1
confirmados; no ejecuta CORE ni modifica `result.json`. La respuesta contiene
`summary`, `status`, `total`, hasta 50 `rows` y `next_cursor`. Las identidades se
validan contra el run, su resultado, diseño, criterios y casos confirmados.

ADR-0040 agrega `attachments.begin`, `attachments.append`, `attachments.finish`,
`attachments.abort`, `attachments.read` y `study.documentation` al protocolo `1.0`.
Los parámetros exhaustivos se generan desde los modelos Pydantic del gateway:

- `begin`: nombre, MIME admitido y tamaño; devuelve `upload_id` UUID de sesión.
- `append`: `upload_id`, offset consecutivo y base64 de hasta 512 KiB; devuelve bytes recibidos.
- `finish`: verifica transferencia y devuelve `FileAttachment` con SHA-256 hexadecimal.
- `abort`: elimina exclusivamente la transferencia temporal; es idempotente.
- `read`: SHA-256 autorizado, offset y longitud de hasta 512 KiB; devuelve base64.
- `study.documentation`: ID completo de experimento; devuelve su configuración documental
  desde la proyección inmutable y habilita la lectura de sus adjuntos en la sesión.

Validar una definición o cargar una plantilla también habilita sus referencias para consulta.
Las referencias ausentes no impiden abrir la definición; impiden su commit hasta resolverse.
El almacén rechaza contenido que no corresponde al MIME declarado y verifica integridad
antes de publicar o consultar. Los adjuntos admitidos son PNG, JPEG, WebP y PDF.
El límite de trama y de bloque no impone un límite al tamaño total de un archivo.

`domain_run.start` reserva y persiste el `domain_run_id` antes de responder `accepted`. Cada
invocación start/resume tiene un `operation_id` nuevo; una ejecución durable puede abarcar varias
operaciones. Los eventos, ordenados por `sequence`, forman la unión discriminada
`generation_started | generation_progress | core_case_started | core_progress | terminal | error`.
`core_case_started` sólo se emite después de persistir el caso y contiene el `core_run_id`.
En SRFL 2, `generation_progress` puede incluir `valid_selections` y
`core_case_started` puede incluir `design_id`, siempre correspondiente al primer
origen del caso CORE. `domain_run.list` devuelve un resumen sin `cases`; conserva
generación y, para SRFL 2, diseños y duración activa.

El draft completo se usa para validar y estimar sin persistencia. Salvo que el usuario active
explícitamente «Guardar como plantilla», `study.prepare` es el primer commit durable y devuelve
el identificador de un experimento independiente según ADR-0051. No existen proyectos, revisiones,
snapshots, sidecars desktop, capabilities versionadas ni API genérica de invocación.

La zona `.domain_attachment_staging/<session>/<upload_id>` contiene únicamente bytes
temporales de transferencias. No guarda el draft ni constituye evidencia confirmada.
Prepare y guardado de plantilla publican archivos bajo `domain_attachments/<sha256>` antes
de confirmar su configuración. El almacenamiento es inmutable y deduplicado; eliminar una
asociación nunca borra archivos confirmados. Los temporales propios se liberan al descartar
la sesión o cerrar normalmente el gateway; un cierre forzado no convierte restos en evidencia.

`templates.save` valida y guarda una configuración como plantilla content-addressed del usuario.
`templates.set_for_run` activa o desactiva como plantilla la configuración inmutable referenciada
por un domain run. Los ejemplos distribuidos continúan siendo plantillas de sólo lectura.
Cada elemento devuelto por `templates.list` identifica explícitamente
`template_id`, `domain_id`, `domain_version` y `name`; las plantillas del usuario
también incluyen `domain_experiment_id`. La UI sólo ofrece como editable una
plantilla cuya versión coincide con su manifest de dominio.

El shell puede registrar más de una UI para un mismo `domain_id`. El selector de
aplicación usa las identidades de `domains.list` y el registro de build; cada
módulo conserva `Screen({host})` y filtra templates y runs por versión. Cambiar
de módulo no agrega comandos ni modifica el protocolo global.
