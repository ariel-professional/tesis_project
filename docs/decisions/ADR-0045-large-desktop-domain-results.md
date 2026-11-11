# ADR-0045 — Resultados de dominio grandes en Desktop

**Estado:** accepted  
**Fecha:** 2026-09-20

## Contexto

El gateway limita cada trama NDJSON a 16 MiB. Un resultado SRFL confirmado con 399 casos ocupa
aproximadamente 29 MiB, por lo que enviarlo como una única respuesta hacía que Electron terminara
el gateway antes de que el renderer pudiera abrirlo. Aumentar el límite trasladaría el problema y
debilitaría la defensa de framing.

## Decisión

- Conservar el límite de 16 MiB por mensaje y el protocolo global `1.2`.
- `domain_run.result` mantiene la respuesta inline cuando cabe en una trama.
- Si no cabe, el gateway valida primero el resultado persistido y devuelve una referencia de
  transporte acotada con el UUID del run, tamaño y SHA-256 del `result.json` inmutable.
- Electron main resuelve exclusivamente `workspace/domain_runs/<uuid>/result.json`, rechaza
  symlinks y escapes, verifica tamaño y SHA-256, y recién entonces parsea el JSON.
- Durante una recarga de desarrollo en la que gateway y Electron main queden temporalmente en
  builds distintas, el host del renderer puede resolver la misma referencia por bloques usando
  el comando acotado `attachments.read`. Verifica tamaño y SHA-256 antes de parsear.
- Los componentes de dominio siguen recibiendo el mismo objeto de resultado; la referencia nunca
  llega a `SingleRowFacilityLayoutScreen` ni modifica su contrato.

## Consecuencias

El tamaño total de un resultado confirmado deja de estar limitado por una trama NDJSON. Las
respuestas pequeñas no cambian, no se duplica evidencia durable y no se habilita lectura arbitraria
del workspace. La lectura por bloques sólo queda autorizada para el resultado solicitado durante
la sesión. La forma genérica `result: JsonValue` del protocolo `1.2` ya admite el descriptor, por lo
que no se agrega un comando ni se modifica el schema del mensaje.
