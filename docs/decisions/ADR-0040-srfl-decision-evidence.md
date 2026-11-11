# ADR-0040 — Antecedentes documentales de decisiones SRFL

**Estado:** accepted  
**Fecha:** 2026-09-09

## Decisión

Se implementa el plan aprobado por el usuario: descripción y antecedentes en estudio,
componentes y diseños SRFL, con edición Desktop, plantillas y consulta desde resultados.
Se extienden explícitamente los contratos pre-release 1.0.0 y el protocolo desktop 1.0.
La descripción existente del estudio se preserva. Los nuevos campos son opcionales;
los adjuntos son archivos PNG/JPEG/WebP/PDF por SHA-256 o enlaces HTTP/HTTPS.
Los metadatos participan en la identidad del experimento, no en los cálculos científicos.

Python conserva la autoridad durable. Las transferencias temporales por sesión preceden
al commit sin persistir el borrador: se permiten archivos temporales, no proyectos ni
sidecars documentales. Los archivos se transfieren en bloques de hasta 512 KiB y no hay
límite de tamaño total impuesto por la aplicación. Prepare y guardado de plantilla
publican archivos inmutables antes que su configuración. OPEN-RETENTION sigue abierto:
solo se limpian transferencias temporales propias, nunca adjuntos confirmados.

La compatibilidad se limita a las dos formas históricas publicadas, antes de adjuntos,
con y sin study.description. Solo son válidas si los nuevos campos están vacíos;
no se omite documentación real para aceptar un hash anterior.

Las plantillas ofrecen dos switches apagados inicialmente: importar adjuntos (archivos
y enlaces de todos los niveles) e importar detalle de restricciones. Los textos de
estudio y diseños se heredan siempre. Cambios propios prevalecen sobre los switches.

## Verificación y pendientes

Por instrucción explícita del usuario, la aceptación utiliza pruebas esenciales sin
umbral de cobertura; no se modifica la configuración global de pytest. La edición y
consulta especializada en CLI, anotaciones y exportación portable quedan pendientes.
Esta decisión no cierra OBJ-17 ni los bloqueos históricos de OBJ-9.
