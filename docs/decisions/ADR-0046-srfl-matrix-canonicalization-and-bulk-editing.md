# ADR-0046 — Canonicalización y carga masiva de matrices SRFL

**Estado:** accepted  
**Fecha:** 2026-09-21  
**Objetivo:** OBJ-17

## Contexto

La UI trataba los pares no dirigidos como equivalentes, pero podía serializar sus
extremos según el orden visual de las estaciones. El dominio exigía que el par
llegara ya ordenado y rechazaba una configuración que el stepper consideraba
válida. La carga celda por celda también resultaba costosa para matrices grandes.

## Decisión

- Toda matriz no dirigida se canonicaliza al crearla, reconciliar estaciones,
  importarla y proyectarla al contrato científico.
- Python repite esa canonicalización antes de validar unicidad y completitud. Dos
  orientaciones del mismo par continúan siendo un duplicado inválido.
- Las matrices dirigidas no se transforman.
- El editor matricial admite selección múltiple y edición individual explícita.
- REL puede usarse como herramienta de carga: una tabla de valores por nivel se
  aplica a una matriz cuantitativa elegida, sin persistir un vínculo ni alterar la
  fórmula de evaluación.
- Los niveles REL sin equivalencia usan cero al maximizar. Al minimizar requieren
  una penalización finita, exacta y mayor que todos los valores declarados.

## Compatibilidad

No cambian los schemas, las versiones ni la representación persistida. Una
configuración ya canónica conserva exactamente sus datos. La aceptación de pares
invertidos amplía la tolerancia de entrada, pero el modelo validado y las nuevas
proyecciones siempre quedan canonicalizados.
