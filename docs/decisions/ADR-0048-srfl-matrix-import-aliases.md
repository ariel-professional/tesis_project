# ADR-0048 — Importación de matrices mediante alias

**Estado:** accepted  
**Fecha:** 2026-09-23  
**Objetivo:** OBJ-17

## Contexto

La importación SRFL 2.0 aceptaba filas basadas en IDs y separaba campos con una
expresión simple. No representaba matrices reales, no ofrecía ejemplos fiables y
podía confundir el orden visible de las estaciones con la identidad científica de
los pares.

## Decisión

- La UI genera para cada estación el prefijo de nombre más corto que sea único.
  Los nombres idénticos reciben sufijos numéricos estables ordenados por ID.
- El alias es exclusivamente visual y nunca se incorpora a `StationV2` ni a los
  schemas científicos. Todo valor importado se resuelve a un ID antes de modificar
  el draft.
- REL admite una lista parcial con encabezado obligatorio y una matriz completa o
  triangular. Las matrices cuantitativas se importan completas y su simetría
  determina automáticamente si son dirigidas.
- La lectura CSV es transaccional y contempla BOM, CRLF/LF, campos citados,
  comillas escapadas y los separadores punto y coma, coma o tabulación.
- La última importación matricial define un orden visual global. Se conserva en el
  draft mediante `clientKey` y, al serializar, se expresa únicamente reordenando la
  lista de estaciones ya prevista por el contrato.
- Las relaciones REL y matrices no dirigidas continúan canonicalizadas conforme a
  ADR-0046; cambiar el orden visible no reasigna ningún valor.

## Compatibilidad

No cambian `schema_version`, `domain.version`, el protocolo del gateway ni los
schemas. Las configuraciones existentes regeneran sus alias de forma
determinística al abrirse y reconstruyen el orden visual desde la lista de
estaciones persistida.
