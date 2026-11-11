# ADR-0026 — Progreso resiliente y diagnósticos internos de workers

- Estado: accepted
- Objetivo afectado: OBJ-17
- Decisiones relacionadas: ADR-0012, ADR-0016 y ADR-0022
- Clase de decisión: `APPROVED_NOW`

## Contexto

El motor de referencia calcula `n! / 2` para estimar candidatos. El canal de
progreso codificaba ambos contadores como enteros binarios sin signo de 64 bits.
Desde `n=21`, el total deja de ser representable y `struct.pack` abortaba el
callback. La excepción atravesaba el motor y luego era descartada por un
`except Exception`, por lo que el runner sólo observaba una terminación genérica.

La configuración podía ser contractual y operacionalmente válida —por ejemplo,
`n=50` y `reference_max_n=100`— aunque la telemetría accesoria no pudiera usar el
formato elegido originalmente.

## Alternativas consideradas

1. Imponer un máximo `n=20` al motor de referencia.
2. Persistir o publicar enteros arbitrarios como parte de un nuevo contrato de
   progreso.
3. Mantener canales internos acotados, ampliar su representación y degradar la
   telemetría sin alterar la ejecución científica.

## Decisión

Se adopta la tercera alternativa.

El canal efímero de progreso conserva tamaño fijo. Cada frame contiene versión,
longitudes y dos campos ASCII decimales canónicos de 309 bytes. El runner
reconstruye enteros Python exactos. Se emite progreso cuando ambos contadores
están entre cero y `int(sys.float_info.max)` y `completed <= total`; esto cubre el
total factorial hasta `n=170`. Para totales mayores —desde `n=171`— el worker no
emite porcentaje: el cómputo, el timeout y la cancelación continúan normalmente.

Una falla de envío o decodificación de progreso es best-effort y nunca se
propaga al motor. No se agrega una cota rígida a `IntegerLimits` ni se cambia
`WorkerRequest`, `WorkerResponse`, `StageProgress` o sus schemas.

Se agrega un segundo canal interno unidireccional y acotado a 32 KiB para fallos
del proceso hijo. Sus registros contienen fase, tipo de excepción, mensaje y
traceback truncados. El proceso padre es el único que escribe `runner.log`:

- con política normal registra fase y tipo;
- con política `debug` agrega mensaje y traceback;
- los resultados persistidos sólo conservan fase y tipo, sin filtrar detalles
  internos ni inventar códigos públicos.

Los fallos inesperados de motor usan `INTERNAL_ERROR`; los de decodificación,
`WORKER_PROTOCOL_ERROR`; y una imposibilidad de entregar respuesta,
`WORKER_TERMINATED`. Se retira el miembro no contractual
`WORKER_PROGRESS_OUT_OF_RANGE`, que no era usado y causaba drift respecto de los
19 schemas `1.0.0` congelados.

## Consecuencias

- `n=50` deja de fallar por la estimación de progreso.
- No existe una cota artificial de ejecución derivada de la interfaz terminal.
- Para `n>=171` no hay porcentaje, pero se preservan timeout y cancelación.
- El canal de fallos sigue siendo interno, acotado y sin acceso del worker al
  workspace.
- Los 19 schemas públicos permanecen byte a byte iguales.

## Trazabilidad

OBJ-17; `src/tesis_proyect/runner/workers.py`; suites de workers, pipeline,
schemas y logging; catálogo público, sección 6.
