# ADR-0053 — Generación bajo demanda de schemas CORE

**Estado:** accepted  
**Fecha:** 2026-11-09

## Decisión

Los schemas JSON del CORE se generan bajo demanda a partir de los modelos Python
con `uv run python scripts/generate_schemas.py`. La salida `schemas/1.0.0/` no
se guarda en este repositorio. Esta decisión sustituye la obligación de conservar
una copia versionada de esos archivos y su comparación automática en CI.

Los modelos, la versión `1.0.0` de los datos y el catálogo público no cambian.
Las pruebas continúan verificando la generación y los contratos de los modelos,
pero ya no existe una comparación automática contra una copia fija anterior.
Los schemas de dominio y del gateway desktop no están incluidos en esta decisión.
