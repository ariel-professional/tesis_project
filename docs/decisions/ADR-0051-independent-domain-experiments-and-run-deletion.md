# ADR-0051 — Experimentos de dominio independientes y borrado manual

Estado: accepted  
Fecha: 2026-10-02

## Contexto

`study.prepare` actualmente reutiliza proyecciones content-addressed por configuración. Esto hace que dos usos de una misma definición compartan identidad aunque sus ejecuciones deban administrarse por separado. El protocolo desktop 1.4 necesita una operación explícita para borrar una ejecución durable.

## Decisión

- Cada preparación crea un experimento de dominio independiente. La proyección nueva guarda `instance_nonce`, 32 caracteres hexadecimales aleatorios (16 bytes), y su ID es SHA-256 de `domain-experiment-instance-v1\0`, nonce, `\0` y la configuración canónica.
- `instance_nonce` es opcional al leer proyecciones previas. Éstas conservan la validación histórica basada en configuración (incluida la forma legacy publicada de SRFL 1); no se migran ni reescriben.
- Reanudar conserva el experimento y sus intentos. La configuración de plantilla no contiene nonce y se mantiene en `domain_templates/`.
- `domain_run.delete` recibe `{domain_run_id}` con UUID completo y responde `{deleted_domain_run_id, deleted_domain_experiment, preserved_template}`. Desde una tarjeta se elimina esa ejecución. Sólo se elimina su proyección si ninguna otra ejecución la referencia. Una plantilla guardada conserva su configuración sin necesitar la proyección.
- El borrado manual enumera referencias y elimina sólo artefactos exclusivos. Se rechaza ante operación activa, lock CORE activo, referencia/ruta no verificable o symlink dentro del árbol afectado. La operación confirmada se registra antes de borrar y se reanuda al abrir el workspace sin ampliar su inventario.
- `OPEN-RETENTION` sigue sin resolver: esta decisión no autoriza limpieza automática ni borrado por antigüedad.

## Consecuencias

Las proyecciones nuevas dejan de ser content-addressed por configuración. La compatibilidad de lectura no implica migración. El borrado requiere coordinación de escritura del workspace entre gateway y CLI, y debe preservar referencias compartidas.
