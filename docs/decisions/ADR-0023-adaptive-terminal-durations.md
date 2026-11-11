# ADR-0023 — Duraciones humanas adaptativas en terminal

- Estado: accepted


- Objetivos afectados: OBJ-15
- Requisitos afectados: RC-01 a RC-07, RNF-04
- Resuelve: ambigüedad visual de tiempos transcurridos y estimados
- Regla normativa: `docs/contracts/public_contract_catalog.md`, sección 5.1
- Supersede: ADR-0016 sólo respecto del formato editorial de duraciones TTY


## Contexto

Rich mostraba dos valores sin etiqueta en formato `H:MM:SS`. Para una búsqueda
factorial, el ETA podía verse como `11827156956:36:41`, sin indicar que eran
horas ni distinguirlo del tiempo transcurrido.

## Decisión

- La terminal etiqueta `Transcurrido` y `Restante estimado`.
- Las duraciones usan unidades en español, pluralización y separadores de miles.
- Segundos muestran segundos; minutos agregan segundos; horas menores a 24
  agregan minutos y segundos.
- Desde un día se muestran sólo las dos unidades significativas mayores:
  días/horas, meses/días o años/meses.
- Un mes equivale a 30 días y un año a 365 días para obtener una representación
  determinista; los años no tienen techo.
- Unidades inferiores con valor cero se omiten.
- Mientras no existe una estimación se muestra `calculando…`.
- La presentación es best-effort, no cambia eventos, timeouts, métricas ni
  evidencia científica.

## Consecuencias

El texto de progreso TTY cambia editorialmente y puede ocupar más ancho, pero los
ETAs extremos se vuelven comprensibles. La conversión de meses/años es una escala
de visualización, no aritmética calendaria.

## Trazabilidad

OBJ-15; `cli/terminal_adapter.py`; pruebas de salida terminal y unidades.
