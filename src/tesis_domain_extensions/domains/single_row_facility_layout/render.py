from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal, localcontext

from tesis_domain_extensions.contracts.results import ExactFraction
from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
    LayoutCaseResult,
    LayoutDesignResult,
    SingleRowFacilityLayoutResult,
)

EM_DASH = "\u2014"


def render_json(result: SingleRowFacilityLayoutResult) -> bytes:
    payload = json.dumps(
        result.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True
    )
    return (payload + "\n").encode("utf-8")


def _linear_forest_paths(edges: list[tuple[str, str]]) -> list[str]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for left, right in edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    paths: list[str] = []
    remaining = set(adjacency)
    while remaining:
        component: set[str] = set()
        pending = [min(remaining)]
        while pending:
            station = pending.pop()
            if station in component:
                continue
            component.add(station)
            pending.extend(adjacency[station] - component)
        endpoint = min(item for item in component if len(adjacency[item]) == 1)
        ordered = [endpoint]
        previous: str | None = None
        while True:
            following = sorted(adjacency[endpoint] - ({previous} if previous else set()))
            following = [item for item in following if item not in ordered]
            if not following:
                break
            previous, endpoint = endpoint, following[0]
            ordered.append(endpoint)
        paths.append(f" {EM_DASH} ".join(min(ordered, list(reversed(ordered)))))
        remaining.difference_update(component)
    return sorted(paths)


def _count_text(case: LayoutCaseResult) -> str:
    count = case.compatible_layout_count
    return str(count.value) if count is not None and count.value is not None else "inconcluso"


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


def _case_label(case: LayoutCaseResult) -> str:
    return ", ".join(case.added_component_ids) or "ninguno"


def _ordered_cases(cases: list[LayoutCaseResult]) -> list[LayoutCaseResult]:
    def key(case: LayoutCaseResult) -> tuple[int, int, int, int, str]:
        count = case.compatible_layout_count
        value = int(count.value) if count is not None and count.value is not None else -1
        return (
            -int(case.total_utility),
            -int(case.utility),
            0 if value >= 0 else 1,
            -value,
            case.case_id,
        )

    return sorted(cases, key=key)


def _human_case(
    case: LayoutCaseResult,
    design: LayoutDesignResult,
    names: dict[str, str],
) -> list[str]:
    paths = "; ".join(
        f" {EM_DASH} ".join(f"{names[item]} ({item})" for item in path)
        for path in case.forest_structure.paths
    )
    isolated = ", ".join(
        f"{names[item]} ({item})" for item in case.forest_structure.isolated_station_ids
    )
    base_utility = int(case.total_utility) - int(case.utility)
    availability = (
        f"    Disponibilidad H_i/H_D: {_fraction_text(case.availability_ratio)} "
        f"({_percent_text(case.availability_ratio)})"
    )
    restrictiveness = (
        "    Restrictividad 1 - H_i/H_D: "
        f"{_fraction_text(case.restrictiveness_ratio)} "
        f"({_percent_text(case.restrictiveness_ratio)})"
    )
    return [
        f"  Caso {case.case_id[:12]}",
        f"    Dise\u00f1o: {design.design_title} ({design.design_id})",
        f"    Base/obligatorios: {', '.join(case.mandatory_component_ids)}",
        f"    A\u00f1adidos: {_case_label(case)}",
        f"    Bosque: {paths}; Libres: {isolated or 'ninguna'}",
        f"    Utilidad incremental: {case.utility} (suma de a\u00f1adidos)",
        (
            f"    Utilidad total: {case.total_utility} = {base_utility} (base) + "
            f"{case.utility} (a\u00f1adidos)"
        ),
        f"    Layouts compatibles: {_count_text(case)}",
        availability,
        restrictiveness,
    ]


def render_human(result: SingleRowFacilityLayoutResult) -> str:
    names = {item.id: item.name for item in result.stations}
    lines = [
        result.study_title,
        f"Ejecuci\u00f3n de dominio: {result.execution.domain_run_id}",
        f"Medida: {result.primary_measure.name}",
    ]
    for design in result.designs:
        base = design.base_layout_count
        base_text = str(base.value) if base is not None and base.value is not None else "inconcluso"
        lines.extend(
            [
                "",
                f"Dise\u00f1o {design.design_id}: {design.design_title}",
                f"  Base: {', '.join(design.mandatory_component_ids)}",
                f"  Layouts base: {base_text}",
                (
                    f"  Combinaciones: {design.theoretical_combinations}; "
                    f"v\u00e1lidas: {design.valid_case_count}; "
                    f"inv\u00e1lidas: {design.invalid_combination_count}"
                ),
                "  C\u00f3mo leer los casos:",
                "    Utilidad incremental = suma de utilidades de los componentes a\u00f1adidos.",
                "    Utilidad total = utilidad de la base + utilidad incremental.",
                "    Disponibilidad = H_i/H_D; restrictividad = 1 - H_i/H_D.",
                "    El bosque enumera las cadenas obligatorias y las estaciones libres.",
                "  Dominancia y frontera de Pareto:",
                "    Se comparan dos objetivos: maximizar utilidad total y layouts compatibles.",
                (
                    "    A domina a B si tiene utilidad total y layouts al menos iguales, "
                    "y mejora estrictamente uno de ellos."
                ),
                (
                    "    La utilidad total e incremental dan el mismo orden dentro del dise\u00f1o "
                    "porque su base es constante."
                ),
                "    La frontera re\u00fane los casos no dominados.",
                "    En ella no puede mejorarse un objetivo sin empeorar al menos el otro.",
                "  Frontera de Pareto:",
                "    Alternativas eficientes entre las que debe elegir el decisor.",
                "    El informe no selecciona autom\u00e1ticamente un mejor caso.",
            ]
        )
        pareto = [case for case in design.cases if case.pareto_optimal]
        for case in _ordered_cases(pareto):
            lines.extend(_human_case(case, design, names))
        if not pareto:
            lines.append("    Inconclusa")
        dominated = [case for case in design.cases if case.dominated]
        lines.extend(
            [
                "  Casos dominados:",
                "    Alternativas excluidas porque otra alternativa del dise\u00f1o las domina.",
            ]
        )
        for case in _ordered_cases(dominated):
            lines.extend(_human_case(case, design, names))
        if not dominated:
            lines.append("    Ninguno")
        lines.append("  Conflictos inv\u00e1lidos:")
        for conflict in design.invalid_conflicts:
            lines.append(
                f"    {conflict.reason}: {conflict.combination_count} combinaciones; "
                f"estaciones: {', '.join(conflict.affected_station_ids)}"
            )
        if not design.invalid_conflicts:
            lines.append("    Ninguno")
    return "\n".join(lines) + "\n"


def _markdown_case_row(case: LayoutCaseResult, design: LayoutDesignResult) -> str:
    paths = "<br>".join(f"`{f' {EM_DASH} '.join(path)}`" for path in case.forest_structure.paths)
    isolated = ", ".join(f"`{item}`" for item in case.forest_structure.isolated_station_ids)
    forest = f"{paths}<br>Libres: {isolated or 'ninguna'}"
    mandatory = ", ".join(f"`{item}`" for item in case.mandatory_component_ids)
    added = ", ".join(f"`{item}`" for item in case.added_component_ids) or "ninguno"
    components = (
        f"Dise\u00f1o: **{design.design_title}** (`{design.design_id}`)<br>"
        f"Base/obligatorios: {mandatory}<br>A\u00f1adidos: {added}"
    )
    return (
        f"| `{case.case_id[:12]}` | {components} | {forest} | {case.utility} | "
        f"{case.total_utility} | {_count_text(case)} | "
        f"{_fraction_text(case.availability_ratio)} ({_percent_text(case.availability_ratio)}) | "
        f"{_fraction_text(case.restrictiveness_ratio)} "
        f"({_percent_text(case.restrictiveness_ratio)}) |"
    )


def _markdown_case_table(cases: list[LayoutCaseResult], design: LayoutDesignResult) -> list[str]:
    lines = [
        (
            "| Caso | Dise\u00f1o y componentes del caso | Bosque | "
            "Utilidad incremental | Utilidad total | "
            "Layouts | Disponibilidad | Restrictividad |"
        ),
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    lines.extend(_markdown_case_row(case, design) for case in _ordered_cases(cases))
    if not cases:
        lines.append("| - | - | - | - | - | - | Inconclusa | Inconclusa |")
    return lines


def _markdown_invalid(design: LayoutDesignResult) -> list[str]:
    lines = [
        "| Causa | Estaciones afectadas | Componentes en conflicto | Combinaciones |",
        "|---|---|---|---:|",
    ]
    for conflict in design.invalid_conflicts:
        lines.append(
            f"| `{conflict.reason}` | {', '.join(conflict.affected_station_ids)} | "
            f"{', '.join(conflict.conflicting_component_ids)} | "
            f"{conflict.combination_count} |"
        )
    if not design.invalid_conflicts:
        lines.append("| Ninguna | - | - | 0 |")
    if design.invalid_combinations is not None:
        lines.extend(["", "Detalle completo:", ""])
        for detail in design.invalid_combinations:
            lines.append(
                f"- `{detail.case_id[:12]}`: {', '.join(detail.added_component_ids)} "
                f"{EM_DASH} `{detail.reason}` en {', '.join(detail.affected_station_ids)}."
            )
    return lines


def render_markdown(result: SingleRowFacilityLayoutResult) -> str:
    lines = [
        f"# {result.study_title}",
        "",
        f"- Ejecuci\u00f3n de dominio: `{result.execution.domain_run_id}`",
        f"- Medida: **{result.primary_measure.name}** (`{result.primary_measure.id}`)",
        f"- Combinaciones te\u00f3ricas: **{result.generation.theoretical_combinations}**",
        f"- Selecciones v\u00e1lidas: **{result.generation.valid_selections}**",
        f"- Combinaciones inv\u00e1lidas: **{result.generation.invalid_combinations}**",
        f"- Casos CORE \u00fanicos: **{result.generation.core_cases}**",
    ]
    for design in result.designs:
        base = design.base_layout_count
        base_text = str(base.value) if base is not None and base.value is not None else "inconcluso"
        mandatory = ", ".join(f"`{item}`" for item in design.mandatory_component_ids)
        candidates = ", ".join(f"`{item}`" for item in design.candidate_component_ids)
        lines.extend(
            [
                "",
                f"## {design.design_title} (`{design.design_id}`)",
                "",
                f"- Componentes obligatorios: {mandatory}",
                f"- Componentes candidatos: {candidates}",
                f"- Combinaciones: **{design.theoretical_combinations}**",
                f"- Casos v\u00e1lidos: **{design.valid_case_count}**",
                f"- Combinaciones inv\u00e1lidas: **{design.invalid_combination_count}**",
                f"- Layouts del dise\u00f1o base: **{base_text}**",
                "",
                "### C\u00f3mo leer los casos v\u00e1lidos",
                "",
                "- **Bosque:** cadenas de estaciones que deben quedar adyacentes. "
                "Las estaciones que no aparecen son `libres` y pueden ubicarse "
                "en cualquier lugar.",
                "- **Utilidad incremental:** suma de utilidades de los componentes a\u00f1adidos.",
                "- **Utilidad total:** utilidad de los componentes base "
                "m\u00e1s la utilidad incremental.",
                "- **Disponibilidad:** `H_i/H_D`, `H_i` layouts válidos del caso "
                "con respecto a los layouts `H_D` "
                "del dise\u00f1o base.",
                "- **Restrictividad:** `1 - H_i/H_D`, proporci\u00f3n de layouts que se pierde "
                "respecto del diseño base.",
                "",
                "### Casos no v\u00e1lidos",
                "",
                *_markdown_invalid(design),
                "",
                "### Dominancia y frontera de Pareto",
                "",
                "Este an\u00e1lisis compara dos objetivos:",
                "- Maximizar la **utilidad total**",
                "- Conservar la mayor cantidad posible de **layouts compatibles**.",
                "",
                "Una alternativa A **domina** a B si A tiene una utilidad total igual o mayor "
                "y cantidad de layouts compatibles iguales o mayores que B, "
                "y es estrictamente mejor "
                "en al menos uno de esos objetivos.",
                "",
                "Dentro de un mismo dise\u00f1o, comparar utilidad total o incremental produce "
                "el mismo orden de dominancia porque la utilidad de la base es constante.",
                "",
                "La **frontera de Pareto** re\u00fane las alternativas no dominadas, "
                "es decir: aquellas en las que no "
                "puede mejorarse un objetivo sin empeorar al menos el otro.",
                "",
                "### Casos v\u00e1lidos dominados",
                "",
                "Alternativas excluidas porque otra alternativa del dise\u00f1o las domina.",
                "",
                *_markdown_case_table([case for case in design.cases if case.dominated], design),
                "",
                "### Frontera de Pareto",
                "",
                "Alternativas eficientes entre las que corresponde elegir seg\u00fan la prioridad "
                "del decisor.",
                "",
                *_markdown_case_table(
                    [case for case in design.cases if case.pareto_optimal], design
                ),
            ]
        )
    return "\n".join([*lines, ""])
