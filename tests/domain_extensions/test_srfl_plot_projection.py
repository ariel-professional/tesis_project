from __future__ import annotations

from fractions import Fraction
from types import SimpleNamespace
from typing import Any

import pytest

from tesis_domain_extensions.domains.single_row_facility_layout.plot_projection import (
    Cell,
    PlotProjection,
    ProjectionRequest,
    _coarsen,
    build_projection,
)
from tesis_domain_extensions.errors import DomainExtensionError


class ProjectionReader:
    def __init__(self, cases: list[dict[str, Any]], frontier: list[dict[str, Any]]) -> None:
        self.cases = cases
        self.frontier = frontier

    def index_count(self, path: str) -> int:
        return len(self.frontier if path == "frontier" else self.cases)

    def page(self, path: str, page: int) -> list[dict[str, Any]]:
        values = self.frontier if path == "frontier" else self.cases
        return values[page * 50 : (page + 1) * 50]


def case(identifier: str, x: int, y: int) -> dict[str, Any]:
    return {
        "case_id": identifier,
        "design_id": "d1",
        "criteria_vector": {
            "x": {"numerator": x, "denominator": 1},
            "y": {"numerator": y, "denominator": 1},
        },
    }


def request(**overrides: Any) -> ProjectionRequest:
    values: dict[str, Any] = {
        "design_id": "d1",
        "x_objective_id": "x",
        "y_objective_id": "y",
        "x_scale": "automatic",
        "y_scale": "automatic",
        "x_log_k": 100.0,
        "y_log_k": 100.0,
    }
    values.update(overrides)
    return ProjectionRequest(**values)


def test_projection_groups_every_dominated_case_and_excludes_frontier() -> None:
    cases = [case("front-a", -4, 9), case("front-b", 10, -3)]
    cases.extend(case(f"dom-{index}", index % 5 - 2, index % 7 - 3) for index in range(17))
    frontier = cases[:2]
    design = SimpleNamespace(
        frontier_index="frontier",
        order_indexes={"case": "cases"},
    )

    projection = build_projection(ProjectionReader(cases, frontier), design, request())
    groups = projection.levels[2]

    assert projection.considered_count == len(cases)
    assert projection.dominated_count == len(cases) - len(frontier)
    assert sum(item["count"] for item in groups) == projection.dominated_count
    assert all(item.get("case_id") not in {"front-a", "front-b"} for item in groups)
    assert {item["case_id"] for item in projection.frontier_positions} == {
        "front-a",
        "front-b",
    }
    assert projection.axes["x"]["minimum"] == {"numerator": "-4", "denominator": "1"}


def test_coarsening_uses_count_weighted_centers_and_preserves_ranges() -> None:
    cells = {
        (0, 0): Cell(1, 0.2, 0.4, Fraction(-3), Fraction(-3), Fraction(2), Fraction(2), "a"),
        (1, 0): Cell(3, 1.8, 1.2, Fraction(-1), Fraction(5), Fraction(4), Fraction(8), None),
    }

    merged = _coarsen(cells, 2)[(0, 0)].as_json()

    assert merged["count"] == 4
    assert merged["x"] == pytest.approx(0.5)
    assert merged["y"] == pytest.approx(0.4)
    assert merged["x_min"] == {"numerator": "-3", "denominator": "1"}
    assert merged["x_max"] == {"numerator": "5", "denominator": "1"}
    assert "case_id" not in merged


def test_projection_sections_are_paged_in_bounded_chunks() -> None:
    groups = tuple({"count": 1, "x": index, "y": index} for index in range(123))
    projection = PlotProjection({}, 123, (), (groups, groups, groups), 123)

    first = projection.page(section="groups", level=2, cursor=0)
    second = projection.page(section="groups", level=2, cursor=50)
    last = projection.page(section="groups", level=2, cursor=100)

    assert len(first["items"]) == len(second["items"]) == 50
    assert len(last["items"]) == 23
    assert first["next_cursor"] == 50
    assert second["next_cursor"] == 100
    assert last["next_cursor"] is None
    with pytest.raises(DomainExtensionError):
        projection.page(section="groups", level=3, cursor=0)


@pytest.mark.parametrize("scale", ["linear", "square-root", "adjusted-log", "percentile"])
def test_projection_handles_negative_values_and_degenerate_axes(scale: str) -> None:
    cases = [case("f", -5, 2), case("a", -2, 2), case("b", 4, 2)]
    design = SimpleNamespace(frontier_index="frontier", order_indexes={"case": "cases"})

    projection = build_projection(
        ProjectionReader(cases, []),
        design,
        request(x_scale=scale, y_scale=scale),
    )

    assert projection.axes["x"]["scale"] == scale
    assert projection.axes["y"]["minimum"] == {"numerator": "2", "denominator": "1"}
    assert projection.frontier_positions == ()
    assert sum(group["count"] for group in projection.levels[2]) == len(cases)
