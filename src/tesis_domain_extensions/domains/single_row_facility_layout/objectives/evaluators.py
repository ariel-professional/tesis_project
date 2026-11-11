from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from decimal import Decimal
from fractions import Fraction
from typing import Literal, cast

from tesis_domain_extensions.contracts.results import ExactFraction

from .contracts import (
    AdjacencyValueContribution,
    AdjacencyValueMatrix,
    AdjacencyValueResult,
    CapturedFlowResult,
    FlowContribution,
    FlowMatrix,
    RelLevelResult,
    RelMatrix,
    RetainedLayoutsResult,
)


def _fraction(numerator: int, denominator: int) -> Fraction:
    if denominator <= 0:
        raise ValueError("el denominador debe ser positivo")
    return Fraction(numerator, denominator)


def evaluate_retained_layouts(
    compatible_layout_count: int | None,
    base_layout_count: int | None,
) -> RetainedLayoutsResult:
    if compatible_layout_count is None or base_layout_count is None:
        return RetainedLayoutsResult(
            objective_id="retained-compatible-layouts",
            objective_version="1",
            status="inconclusive",
            unit="fracción exacta",
            direction="maximize",
            diagnostics=["Falta evidencia CORE."],
        )
    if (
        base_layout_count <= 0
        or compatible_layout_count < 0
        or compatible_layout_count > base_layout_count
    ):
        return RetainedLayoutsResult(
            objective_id="retained-compatible-layouts",
            objective_version="1",
            status="invalid",
            unit="fracción exacta",
            direction="maximize",
            diagnostics=["Los conteos no forman una proporción válida."],
        )
    ratio = _fraction(compatible_layout_count, base_layout_count)
    return RetainedLayoutsResult(
        objective_id="retained-compatible-layouts",
        objective_version="1",
        status="conclusive",
        compatible_layout_count=compatible_layout_count,
        base_layout_count=base_layout_count,
        fraction=ExactFraction(numerator=ratio.numerator, denominator=ratio.denominator),
        unit="fracción exacta",
        direction="maximize",
    )


def evaluate_rel_closeness(
    matrix: RelMatrix,
    prescribed_edges: Iterable[tuple[str, str]],
) -> dict[str, RelLevelResult]:
    prescribed = {tuple(sorted(edge)) for edge in prescribed_edges}
    eligible = [item for item in matrix.requirements if item.level in {"A", "E", "I", "O"}]
    totals = Counter(item.level for item in eligible)
    result: dict[str, RelLevelResult] = {}
    for level, denominator in sorted(totals.items()):
        level_pairs = {
            (item.first_station_id, item.second_station_id)
            for item in eligible
            if item.level == level
        }
        guaranteed = sorted(level_pairs.intersection(prescribed))
        pending = sorted(level_pairs - prescribed)
        numerator = len(guaranteed)
        ratio = _fraction(numerator, denominator)
        result[level] = RelLevelResult(
            objective_id=f"rel-closeness-{level.lower()}",
            objective_version="1",
            level=cast(Literal["A", "E", "I", "O"], level),
            status="conclusive",
            numerator=numerator,
            denominator=denominator,
            fraction=ExactFraction(numerator=ratio.numerator, denominator=ratio.denominator),
            guaranteed_pairs=guaranteed,
            pending_pairs=pending,
            unit=f"fracción exacta REL {level}",
            direction="maximize",
        )
    return result


def evaluate_adjacency_flow(
    matrix: FlowMatrix,
    prescribed_edges: Iterable[tuple[str, str]],
) -> CapturedFlowResult:
    prescribed = {tuple(sorted(edge)) for edge in prescribed_edges}
    total = Decimal("0")
    entries = {(item.from_station_id, item.to_station_id): item.quantity for item in matrix.entries}
    contributions: list[FlowContribution] = []
    for first, second in sorted(prescribed):
        forward = entries.get((first, second), Decimal("0"))
        reverse = entries.get((second, first)) if matrix.directed else None
        pair_total = forward + (reverse if reverse is not None else Decimal("0"))
        total += pair_total
        contributions.append(
            FlowContribution(
                first_station_id=first,
                second_station_id=second,
                forward_quantity=forward,
                reverse_quantity=reverse,
                total=pair_total,
            )
        )
    return CapturedFlowResult(
        objective_id="captured-adjacency-flow",
        objective_version="1",
        status="conclusive",
        total=total,
        unit=matrix.unit,
        horizon=matrix.horizon,
        directed=matrix.directed,
        direction="maximize",
        contributions=contributions,
    )


def evaluate_adjacency_value(
    matrix: AdjacencyValueMatrix,
    prescribed_edges: Iterable[tuple[str, str]],
) -> AdjacencyValueResult:
    prescribed = {tuple(sorted(edge)) for edge in prescribed_edges}
    total = Decimal("0")
    entries = {(item.from_station_id, item.to_station_id): item.value for item in matrix.entries}
    contributions: list[AdjacencyValueContribution] = []
    for first, second in sorted(prescribed):
        forward = entries.get((first, second), Decimal("0"))
        reverse = entries.get((second, first)) if matrix.directed else None
        pair_total = forward + (reverse if reverse is not None else Decimal("0"))
        total += pair_total
        contributions.append(
            AdjacencyValueContribution(
                first_station_id=first,
                second_station_id=second,
                forward_value=forward,
                reverse_value=reverse,
                total=pair_total,
            )
        )
    return AdjacencyValueResult(
        objective_id=f"adjacency-{matrix.id}",
        objective_version="1",
        matrix_id=matrix.id,
        status="conclusive",
        total=total,
        unit=matrix.unit,
        reference_period=matrix.reference_period,
        directed=matrix.directed,
        direction=matrix.direction,
        contributions=contributions,
    )
