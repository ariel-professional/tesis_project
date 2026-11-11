from __future__ import annotations

import json
from decimal import Decimal, localcontext

from tesis_domain_extensions.contracts.results import ExactFraction
from tesis_domain_extensions.domains.inspection_route.contracts import (
    InspectionRouteResult,
    InspectionScenarioResult,
)


def render_json(result: InspectionRouteResult) -> bytes:
    payload = json.dumps(
        result.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True
    )
    return (payload + "\n").encode("utf-8")


def _fraction_text(value: ExactFraction | None) -> str:
    return "inconclusa" if value is None else f"{value.numerator}/{value.denominator}"


def _percent_text(value: ExactFraction | None) -> str:
    if value is None:
        return "inconcluso"
    numerator, denominator = int(value.numerator), int(value.denominator)
    with localcontext() as context:
        context.prec = max(len(str(numerator)), len(str(denominator))) + 8
        percent = Decimal(numerator) * Decimal(100) / Decimal(denominator)
    return f"{percent:.2f} %"


def _count_text(scenario: InspectionScenarioResult) -> str:
    count = scenario.route_count
    return str(count.value) if count is not None and count.value is not None else "inconcluso"


def _feasibility(value: str) -> str:
    return {
        "feasible": "factible",
        "invalid_constraints": "restricciones incompatibles",
        "inconclusive": "inconcluso",
    }[value]


def _scenario_human(
    scenario: InspectionScenarioResult,
    names: dict[str, str],
    *,
    highlighted: bool,
) -> list[str]:
    lines = [
        "",
        f"Escenario {scenario.scenario_id}: {scenario.scenario_title}",
        f"  Estado: {_feasibility(scenario.feasibility)}",
    ]
    if highlighted:
        lines.append("  Comparación: máxima flexibilidad del estudio")
    if scenario.validation_issue is not None:
        issue = scenario.validation_issue
        lines.extend(
            [
                "  Ejecución CORE: omitida",
                f"  Causa: {issue.message}",
                "  Instalaciones afectadas: "
                + ", ".join(names[item] for item in issue.affected_location_ids),
            ]
        )
        return lines
    lines.append(f"  Recorridos admisibles: {_count_text(scenario)}")
    measure = scenario.retained_route_flexibility
    fraction = None if measure is None else measure.value
    lines.append(
        f"  Flexibilidad conservada: {_fraction_text(fraction)} ({_percent_text(fraction)})"
    )
    if scenario.structure is not None:
        chains = [
            " → ".join(names[item] for item in chain)
            for chain in scenario.structure.mandatory_chains
        ]
        lines.append(f"  Cadenas obligatorias: {'; '.join(chains) or 'ninguna'}")
        free = ", ".join(names[item] for item in scenario.structure.unconstrained_locations)
        lines.append(f"  Instalaciones libres: {free or 'ninguna'}")
    return lines


def render_human(result: InspectionRouteResult) -> str:
    names = {item.id: item.name for item in result.locations}
    lines = [
        result.study_title,
        f"Ejecución de dominio: {result.execution.domain_run_id}",
        f"Escenarios declarados: {result.generation.declared_scenarios}",
        f"Escenarios válidos: {result.generation.valid_scenarios}",
        f"Escenarios inválidos omitidos: {result.generation.invalid_scenarios}",
        f"Casos CORE únicos: {result.generation.core_cases}",
        f"Comparación: {result.comparison_status}",
    ]
    if result.most_flexible_scenario_ids:
        lines.append("Máxima flexibilidad: " + ", ".join(result.most_flexible_scenario_ids))
    elif result.comparison_status != "conclusive":
        lines.append("Máxima flexibilidad: no determinada")
    highlighted = set(result.most_flexible_scenario_ids)
    for scenario in result.scenarios:
        lines.extend(
            _scenario_human(scenario, names, highlighted=scenario.scenario_id in highlighted)
        )
    lines.extend(["", f"Alcance: {result.limitations[0].message}"])
    return "\n".join(lines) + "\n"


def _scenario_markdown(
    scenario: InspectionScenarioResult,
    names: dict[str, str],
    *,
    highlighted: bool,
) -> list[str]:
    lines = [
        f"## {scenario.scenario_title} (`{scenario.scenario_id}`)",
        "",
        f"- Estado: **{_feasibility(scenario.feasibility)}**",
        f"- Conjunto de obligaciones: `{scenario.constraint_set_id}`",
    ]
    if highlighted:
        lines.append("- Comparación: **máxima flexibilidad del estudio**")
    if scenario.validation_issue is not None:
        issue = scenario.validation_issue
        affected = ", ".join(f"{names[item]} (`{item}`)" for item in issue.affected_location_ids)
        conflicts = ", ".join(
            f"`{first}` / `{second}`" for first, second in issue.conflicting_consecutive_visits
        )
        lines.extend(
            [
                "- Ejecución CORE: **omitida**",
                f"- Causa: {issue.message}",
                f"- Instalaciones afectadas: {affected or 'ninguna'}",
                f"- Obligaciones en conflicto: {conflicts or 'ninguna'}",
                "",
            ]
        )
        return lines
    measure = scenario.retained_route_flexibility
    fraction = None if measure is None else measure.value
    lines.extend(
        [
            f"- Run CORE: `{scenario.core_run_id}`",
            f"- Recorridos admisibles: **{_count_text(scenario)}**",
            (
                "- Flexibilidad conservada: "
                f"**{_fraction_text(fraction)}** ({_percent_text(fraction)})"
            ),
            "",
            "### Estructura",
            "",
        ]
    )
    if scenario.structure is None:
        lines.append("No existe un análisis estructural confirmado.")
    else:
        if scenario.structure.mandatory_chains:
            lines.extend(
                "- " + " → ".join(names[item] for item in chain)
                for chain in scenario.structure.mandatory_chains
            )
        else:
            lines.append("- Sin cadenas obligatorias")
        free = ", ".join(names[item] for item in scenario.structure.unconstrained_locations)
        lines.append(f"- Instalaciones libres: {free or 'ninguna'}")
        lines.append(f"- Bloques reordenables: {scenario.structure.planning_blocks}")
    lines.append("")
    return lines


def render_markdown(result: InspectionRouteResult) -> str:
    names = {item.id: item.name for item in result.locations}
    maximum = (
        ", ".join(f"`{item}`" for item in result.most_flexible_scenario_ids) or "no determinada"
    )
    lines = [
        f"# {result.study_title}",
        "",
        f"- Ejecución de dominio: `{result.execution.domain_run_id}`",
        f"- Medida: **{result.primary_measure.name}** (`{result.primary_measure.id}`)",
        f"- Escenarios declarados: **{result.generation.declared_scenarios}**",
        f"- Escenarios válidos: **{result.generation.valid_scenarios}**",
        f"- Escenarios inválidos omitidos: **{result.generation.invalid_scenarios}**",
        f"- Conjuntos duplicados reutilizados: **{result.generation.duplicate_constraint_sets}**",
        f"- Casos CORE únicos: **{result.generation.core_cases}**",
        f"- Estado de comparación: **{result.comparison_status}**",
        f"- Máxima flexibilidad: {maximum}",
        "",
    ]
    highlighted = set(result.most_flexible_scenario_ids)
    for scenario in result.scenarios:
        lines.extend(
            _scenario_markdown(
                scenario,
                names,
                highlighted=scenario.scenario_id in highlighted,
            )
        )
    lines.extend(["## Alcance", "", result.limitations[0].message, ""])
    return "\n".join(lines)
