# ADR-0042 — Selector de aplicación y modelo SRFL

- Estado: accepted
- Fecha: 2026-09-17
- Objetivo: OBJ-17
- Reemplaza parcialmente: ADR-0035 y ADR-0041

## Contexto

SRFL dispone de dos contratos científicos válidos y distintos. La integración
inicial de `2.0.0` reemplazó la única UI registrada y limitó `1.0.0` a resultados
históricos. Esa política no satisface el requisito de poder elegir qué
aplicación/modelo completo se utiliza desde el escritorio.

## Decisión

El shell muestra un selector **Aplicación / modelo** con cada identidad SRFL
instalada. Elegir `1.0.0` o `2.0.0` carga mediante el registro lazy un módulo UI
independiente y muestra un loader durante el cambio.

Cada módulo conserva su contrato completo:

- `1.0.0` permite crear, importar, validar, preparar, ejecutar, reanudar y
  consultar estudios con utilidades y Pareto bidimensional;
- `2.0.0` ofrece criterios tipados, REL, flujo, políticas `X` y Pareto
  multidimensional;
- templates, runs, drafts y resultados se filtran por `domain.version`; no hay
  conversión automática entre versiones;
- cambiar el selector desmonta la UI actual. La evidencia durable permanece en
  el workspace, pero un borrador todavía no preparado sigue siendo sólo memoria.

El registro admite varios manifests first-party confinados bajo el mismo
directorio `ui/`, uno por `(domain_id, domain_version)`. El protocolo gateway
continúa siendo global `1.1`: `domains.list`, `templates.list` y los manifests
durables ya contienen la identidad necesaria y no requieren comandos nuevos.

## Consecuencias

Quedan reemplazadas la exclusividad de la UI v2 y la restricción de v1 a sólo
lectura establecidas en ADR-0041. Sus decisiones científicas para v2 permanecen
vigentes. ADR-0035 continúa vigente salvo por la interpretación de “una UI” como
una sola versión por dominio: ahora cada identidad registrada carga su propio
módulo, manteniendo `Screen({host})` y el host nominado.

Los schemas científicos `1.0.0` siguen congelados; restaurar su editor no cambia
ni reinterpreta esos contratos.
