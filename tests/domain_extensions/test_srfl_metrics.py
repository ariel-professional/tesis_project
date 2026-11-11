from __future__ import annotations

import io
import json
from itertools import combinations
from pathlib import Path
from threading import Event
from typing import Any
from uuid import uuid4

import pytest

from tesis_domain_extensions.domains.single_row_facility_layout.metrics import analyze_metric


@pytest.mark.parametrize(
    "version,mode", [("2.0.0", None), ("2.1.0", "standard"), ("2.1.0", "high_performance")]
)
def test_flexibility_gateway_uses_confirmed_counts_without_retention(
    tmp_path: Path, version: str, mode: str | None
) -> None:
    from tesis_desktop_gateway.server import GatewayServer

    payload = json.loads(
        Path("examples/domains/single-row-facility-layout/v2-complete.json").read_bytes()
    )
    payload["schema_version"] = version
    payload["domain"]["version"] = version
    payload["study"] = {
        "id": "counts",
        "title": "Counts",
        "stations": [{"id": s, "name": s.upper()} for s in "abcd"],
        "components": [{"id": "ab", "station_ids": ["a", "b"]}],
        "designs": [{"id": "design-a", "title": "A", "base_component_ids": []}],
    }
    payload["decision_model"] = {
        "selected_objectives": [{"id": "captured-adjacency-flow", "version": "1"}],
        "adjacency_flow": [
            {
                "id": "gain",
                "name": "Gain",
                "description": "Gain",
                "direction": "maximize",
                "unit": "u",
                "provenance": "test",
                "directed": False,
                "entries": [
                    {
                        "from_station_id": a,
                        "to_station_id": b,
                        "value": "1" if (a, b) == ("a", "b") else "0",
                    }
                    for a, b in combinations("abcd", 2)
                ],
            }
        ],
    }
    if mode:
        payload["execution"]["mode"] = mode
    ready = Event()

    class ReplyOutput(io.BytesIO):
        def flush(self) -> None:
            super().flush()
            ready.set()

    output = ReplyOutput()
    server = GatewayServer(tmp_path, input_stream=io.BytesIO(), output_stream=output)
    application = server.application
    try:
        prepared = application.prepare_payload(json.dumps(payload).encode())
        interpreted = application.run(prepared.domain_experiment_id)
        root = tmp_path / "domain_runs" / interpreted.manifest.domain_run_id
        before = {p.name: p.read_bytes() for p in root.glob("*.json")}
        server._handle_frame(
            json.dumps(
                {
                    "protocol_version": "1.5",
                    "message_type": "request",
                    "request_id": str(uuid4()),
                    "command": "domain_run.metrics",
                    "params": {
                        "domain_run_id": interpreted.manifest.domain_run_id,
                        "metric_id": "base-flexibility",
                        "design_id": "design-a",
                        "cursor": 0,
                    },
                }
            ).encode()
        )
        assert ready.wait(5), "gateway did not reply"
        reply = json.loads(output.getvalue())
        assert reply["status"] == "success", reply
        result = reply["result"]
        assert result["status"] == "conclusive"
        assert result["summary"]["base_layout_count"] == 12
        assert result["summary"]["missing_cases"] == 0
        assert [(row["numerator"], row["denominator"]) for row in result["rows"]] == [(1, 2)]
        assert before == {p.name: p.read_bytes() for p in root.glob("*.json")}
    finally:
        application.close()
        server.attachments.close()


def objective(identifier: str, direction: str = "maximize") -> dict[str, object]:
    return {
        "definition": {"id": identifier, "name": identifier, "direction": direction, "unit": "u"}
    }


def case(
    identifier: str,
    values: dict[str, dict[str, int]],
    *,
    frontier: bool,
    edges: list[list[str]] | None = None,
    components: list[str] | None = None,
) -> dict[str, object]:
    return {
        "case_id": identifier,
        "forest_id": f"forest-{identifier}",
        "criteria_vector": values,
        "pareto_optimal": frontier,
        "edges": edges or [],
        "component_ids": components or [],
        "added_component_ids": components or [],
    }


def design(cases: list[dict[str, object]]) -> dict[str, object]:
    return {"design_id": "design-a", "cases": cases, "base_layout_count": 10}


@pytest.mark.parametrize("design_count", [0, 1, 3])
def test_shared_patterns_read_each_design_once_and_preserve_pages(design_count: int) -> None:
    class TrackedDesign(dict[str, Any]):
        reads = 0

        def get(self, key: str, default: Any = None) -> Any:
            if key == "cases":
                self.reads += 1
            return super().get(key, default)

    designs = [
        TrackedDesign(
            design_id=f"d{i}",
            cases=[
                case("base", {}, frontier=False, edges=[["a", "b"]]),
                case(
                    "frontier",
                    {},
                    frontier=True,
                    edges=[["a", "b"], *[["x", f"s{j}"] for j in range(52)]],
                    components=["optional"],
                ),
                case("absent", {}, frontier=False, edges=[["y", "z"]], components=["absent"]),
            ],
        )
        for i in range(design_count)
    ]
    params: dict[str, Any] = dict(
        metric_id="shared-design-patterns",
        design_id=None,
        criterion_id=None,
        case_id=None,
        designs=designs,
        objectives=[],
    )
    result = analyze_metric(cursor=0, **params)
    assert all(item.reads == 1 for item in designs)
    assert result["total"] == (54 if design_count else 0)
    assert len(result["rows"]) == (50 if design_count else 0)
    if designs:
        tail = analyze_metric(cursor=50, **params)
        assert len(tail["rows"]) == 4
        assert tail["next_cursor"] is None
        states = {
            row["adjacency"]: row["designs"][0]["state"] for row in [*result["rows"], *tail["rows"]]
        }
        assert states["a\u2013b"] == "obligatoria"
        assert states["s0\u2013x"] == "presente en frontera"
        assert states["y\u2013z"] == "opcional y ausente"
        filtered = analyze_metric(cursor=0, **{**params, "design_id": "d0"})
        assert filtered["summary"]["designs"] == 1
    with pytest.raises(ValueError, match="diseño"):
        analyze_metric(cursor=0, **{**params, "design_id": "missing"})


def test_fraction_and_directional_extremes_are_exact_and_ties_are_kept() -> None:
    huge = 10**30
    rows = [
        case("a", {"gain": {"numerator": str(huge), "denominator": "3"}}, frontier=True),
        case("b", {"gain": {"numerator": huge, "denominator": 3}}, frontier=True),
        case("c", {"gain": {"numerator": -huge, "denominator": 7}}, frontier=True),
        case("d", {"gain": {"numerator": huge * 2, "denominator": 3}}, frontier=False),
    ]
    result = analyze_metric(
        metric_id="criterion-extremes",
        design_id="design-a",
        criterion_id="gain",
        case_id=None,
        cursor=0,
        designs=[design(rows)],
        objectives=[objective("gain", "maximize")],
    )
    extreme = result["rows"][0]
    assert extreme["best"] == f"{huge}/3"
    assert extreme["best_case_ids"] == ["a", "b"]
    assert extreme["worst"] == f"-{huge}/7"


def test_metric_pages_are_bounded_to_fifty_rows() -> None:
    components = [f"c{index}" for index in range(12)]
    result = analyze_metric(
        metric_id="component-cooccurrence",
        design_id="design-a",
        criterion_id=None,
        case_id=None,
        cursor=0,
        designs=[
            design(
                [
                    case("a", {}, frontier=True, components=components),
                    case("b", {}, frontier=True, components=["c10", "c11"]),
                ]
            )
        ],
        objectives=[],
    )
    assert result["total"] == 66
    assert len(result["rows"]) == 50
    assert result["next_cursor"] == 50
    assert result["rows"][0]["components"] == ["c10", "c11"]
    assert result["rows"][0]["together"] == 2


def test_pareto_presence_sorts_each_kind_before_paginating() -> None:
    cases = [
        case("base", {}, frontier=True),
        case("a", {}, frontier=True, edges=[["a", "b"], ["b", "c"]], components=["one", "many"]),
        case("b", {}, frontier=True, edges=[["a", "b"]], components=["one"]),
    ]
    result = analyze_metric(
        metric_id="pareto-presence",
        design_id="design-a",
        criterion_id=None,
        case_id=None,
        cursor=0,
        designs=[design(cases)],
        objectives=[],
    )
    assert [(row["kind"], row["id"], row["count"]) for row in result["rows"]] == [
        ("adjacency", "a\u2013b", 2),
        ("adjacency", "b\u2013c", 1),
        ("component", "one", 2),
        ("component", "many", 1),
    ]


def test_flexibility_distribution_uses_complete_frontier_and_exact_large_counts() -> None:
    base = 10**40
    cases = []
    for index in range(52):
        item = case(f"c{index}", {}, frontier=True)
        item["compatible_layout_count"] = base * (index % 5) // 4
        cases.append(item)
    item_design = design(cases)
    item_design["base_layout_count"] = base
    result = analyze_metric(
        metric_id="base-flexibility",
        design_id="design-a",
        criterion_id=None,
        case_id=None,
        cursor=0,
        designs=[item_design],
        objectives=[],
    )
    assert result["status"] == "conclusive"
    assert len(result["rows"]) == 50
    assert result["next_cursor"] == 50
    assert result["rows"][0]["numerator"] == 1
    assert result["rows"][0]["denominator"] == 1
    last_page = analyze_metric(
        metric_id="base-flexibility",
        design_id="design-a",
        criterion_id=None,
        case_id=None,
        cursor=50,
        designs=[item_design],
        objectives=[],
    )
    assert [row["numerator"] for row in last_page["rows"]] == [0, 0]
    assert result["summary"]["base_layout_count"] == str(base)
    assert [bucket["count"] for bucket in result["summary"]["distribution"]] == [
        11,
        11,
        10,
        20,
    ]
    assert result["summary"]["focus_distribution"] is None


def test_flexibility_focus_reveals_low_values_with_a_hundred_percent_outlier() -> None:
    item_design = design([])
    item_design["base_layout_count"] = 10_000
    cases = []
    for index in range(12):
        item = case(f"low-{index}", {}, frontier=True)
        item["compatible_layout_count"] = (index % 7 + 1) * 100
        cases.append(item)
    base_case = case("base", {}, frontier=True)
    base_case["compatible_layout_count"] = 10_000
    item_design["cases"] = [*cases, base_case]
    result = analyze_metric(
        metric_id="base-flexibility",
        design_id="design-a",
        criterion_id=None,
        case_id=None,
        cursor=0,
        designs=[item_design],
        objectives=[],
    )
    assert result["status"] == "conclusive"
    assert [bucket["count"] for bucket in result["summary"]["distribution"]] == [12, 0, 0, 1]
    focus = result["summary"]["focus_distribution"]
    assert focus["upper_percent"] == 10
    assert focus["within_cases"] == 12
    assert focus["above_cases"] == 1
    assert focus["counts"] == [2, 4, 4, 2, 0]


def test_flexibility_missing_count_is_inconclusive_not_zero() -> None:
    known = case("known", {}, frontier=True)
    known["retained_layouts"] = {
        "status": "conclusive",
        "compatible_layout_count": 5,
    }
    missing = case("missing", {}, frontier=True)
    missing["criteria_vector"] = {"retained-compatible-layouts": {"numerator": 0, "denominator": 1}}
    result = analyze_metric(
        metric_id="base-flexibility",
        design_id="design-a",
        criterion_id=None,
        case_id=None,
        cursor=0,
        designs=[design([known, missing])],
        objectives=[],
    )
    assert result["status"] == "inconclusive"
    assert result["summary"]["missing_cases"] == 1
    assert result["summary"]["distribution"][2]["count"] == 1
    assert len(result["rows"]) == 1
    assert result["rows"][0]["case_id"] == "known"


def test_sensitivity_reclassifies_all_cases_after_removing_selected_criterion() -> None:
    cases = [
        case(
            "a",
            {"x": {"numerator": 10, "denominator": 1}, "y": {"numerator": 1, "denominator": 1}},
            frontier=True,
        ),
        case(
            "c",
            {"x": {"numerator": 9, "denominator": 1}, "y": {"numerator": 1, "denominator": 1}},
            frontier=False,
            components=["corte-ensamble"],
        ),
    ]
    result = analyze_metric(
        metric_id="pareto-sensitivity",
        design_id="design-a",
        criterion_id="x",
        case_id=None,
        cursor=0,
        designs=[design(cases)],
        objectives=[objective("x"), objective("y")],
    )
    assert result["summary"]["official_frontier"] == 1
    assert result["summary"]["alternative_frontier"] == 2
    assert {row["case_id"] for row in result["rows"]} == {"a", "c"}
    assert {row["status"] for row in result["rows"]} == {"remains", "enters"}
    assert next(row for row in result["rows"] if row["case_id"] == "c")["added_component_ids"] == [
        "corte-ensamble"
    ]
