# ADR-0050 — Proyección progresiva del gráfico SRFL de alto rendimiento

**Estado:** accepted  
**Fecha:** 2026-09-30  
**Objetivo:** OBJ-17

## Contexto

El gráfico SRFL 2.1 de alto rendimiento cargaba todos los puntos en el renderer y
resolvía escalas automáticas comparando pares. Esto demora la frontera, escala de
forma cuadrática y no limita las marcas SVG cuando hay decenas de miles de casos.

## Decisión

- La frontera exacta se presenta completa, sin agrupar. Los casos dominados se
  presentan en cuadrículas anidadas 16×8, 32×16 y 64×32. Cada celda representa
  cantidad, centro transformado y rangos de valores originales; los niveles se
  sustituyen entre sí. Una celda singleton conserva su `case_id`.
- El backend proyecta todos los valores del diseño con escalas y límites comunes,
  calcula ocupación en tiempo lineal por cada combinación de escalas y conserva en
  memoria una sola proyección por run/diseño/ejes/parámetros. No agrega artefactos
  persistidos. Las secciones y agrupaciones se sirven en páginas de hasta 50.
- El SVG muestra la frontera directamente mientras se prepara la proyección.
  Agrupaciones múltiples no se comportan como casos y no abren detalle.
- El gateway desktop incorpora `domain_run.plot_projection` y sube de `1.3` a
  `1.4`. `domain_run.plot_points` permanece disponible y SRFL sigue en versión
  `2.1.0` con sus resultados confirmados sin cambios.

## Consecuencias

La memoria de la proyección agrupada queda acotada por 2.048 celdas; las posiciones
de frontera permanecen completas porque no se permite omitir casos no dominados.
Cambiar nivel reutiliza el cálculo; cambiar diseño, ejes o escala reemplaza la
proyección retenida.
