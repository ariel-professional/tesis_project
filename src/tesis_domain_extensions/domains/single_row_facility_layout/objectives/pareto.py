from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

Direction = Literal["maximize", "minimize"]


@dataclass(frozen=True)
class ParetoPoint:
    case_id: str
    values: dict[str, Fraction]


def _at_least_as_good(left: Fraction, right: Fraction, direction: Direction) -> bool:
    return left >= right if direction == "maximize" else left <= right


def dominates(
    candidate: ParetoPoint,
    other: ParetoPoint,
    directions: dict[str, Direction],
) -> bool:
    if set(candidate.values) != set(directions) or set(other.values) != set(directions):
        raise ValueError("todos los puntos deben tener todas las dimensiones activas")
    comparisons = [
        _at_least_as_good(candidate.values[key], other.values[key], directions[key])
        for key in directions
    ]
    strict = [candidate.values[key] != other.values[key] for key in directions]
    return all(comparisons) and any(strict)


def classify_pareto(
    points: Sequence[ParetoPoint], directions: dict[str, Direction]
) -> dict[str, tuple[bool, list[str]]]:
    """Return ``case_id -> (dominated, dominators)`` using exact values."""

    result: dict[str, tuple[bool, list[str]]] = {}
    for point in points:
        dominators = [
            other.case_id
            for other in points
            if other.case_id != point.case_id and dominates(other, point, directions)
        ]
        result[point.case_id] = (bool(dominators), sorted(dominators))
    return result
