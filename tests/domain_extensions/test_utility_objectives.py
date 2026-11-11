import json
from decimal import Decimal
from fractions import Fraction
from itertools import permutations
from pathlib import Path

import pytest

from tesis_domain_extensions.domains.single_row_facility_layout.objectives.contracts import (
    AdjacencyValueEntry,
    AdjacencyValueMatrix,
    FlowEntry,
    FlowMatrix,
    RelMatrix,
    RelRequirement,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.evaluators import (
    _fraction,
    evaluate_adjacency_flow,
    evaluate_adjacency_value,
    evaluate_rel_closeness,
    evaluate_retained_layouts,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.pareto import (
    ParetoPoint,
    classify_pareto,
)


def _execution() -> dict[str, object]:
    return {
        "counting_convention": "undirected_paths_reverse_identified",
        "methods": {"exact": {"engine": "auto"}, "reference": {"engine": "bruteforce_python_v1"}},
        "persistence": {"policy": "normal", "persist_events": False},
        "integer_limits": {
            "max_n": 12,
            "reference_max_n": 10,
            "exact_timeout_ms": 30000,
            "reference_timeout_ms": 30000,
            "cancellation_grace_ms": 1000,
            "control_connect_timeout_ms": 1000,
            "control_response_timeout_ms": 1000,
            "control_max_message_bytes": 16384,
            "input_max_bytes": 1048576,
            "event_max_payload_bytes": 65536,
            "worker_max_message_bytes": 65536,
            "runner_log_max_bytes": 5242880,
            "runner_log_backup_count": 3,
        },
    }


def test_retained_layouts_is_an_exact_fraction() -> None:
    result = evaluate_retained_layouts(2, 6)
    assert result.fraction is not None
    assert result.fraction.numerator == 1
    assert result.fraction.denominator == 3
    assert result.compatible_layout_count == 2
    assert result.base_layout_count == 6


def test_rel_is_symmetric_and_separated_by_level() -> None:
    matrix = RelMatrix(
        requirements=[
            RelRequirement(
                first_station_id="a", second_station_id="b", level="A", reason="r", provenance="p"
            ),
            RelRequirement(
                first_station_id="a", second_station_id="c", level="A", reason="r", provenance="p"
            ),
            RelRequirement(
                first_station_id="b", second_station_id="c", level="E", reason="r", provenance="p"
            ),
        ]
    )
    values = evaluate_rel_closeness(matrix, [("b", "a"), ("b", "c")])
    assert values["A"].fraction.numerator == 1
    assert values["A"].fraction.denominator == 2
    assert values["A"].guaranteed_pairs == [("a", "b")]
    assert values["A"].pending_pairs == [("a", "c")]
    assert values["E"].fraction.numerator == 1
    assert values["E"].fraction.denominator == 1


def test_directed_flow_sums_both_directions_once_per_prescribed_pair() -> None:
    matrix = FlowMatrix(
        unit="pieces",
        horizon="hour",
        provenance="production records",
        directed=True,
        entries=[
            FlowEntry(from_station_id="a", to_station_id="b", quantity=Decimal("70")),
            FlowEntry(from_station_id="b", to_station_id="a", quantity=Decimal("50")),
            FlowEntry(from_station_id="a", to_station_id="c", quantity=Decimal("99")),
        ],
    )
    result = evaluate_adjacency_flow(matrix, [("a", "b")])
    assert result.total == Decimal("120")
    assert result.contributions[0].forward_quantity == Decimal("70")
    assert result.contributions[0].reverse_quantity == Decimal("50")


def test_rel_excludes_u_and_x_from_objective_dimensions() -> None:
    matrix = RelMatrix(
        requirements=[
            RelRequirement(
                first_station_id="a", second_station_id="b", level="U", reason="r", provenance="p"
            ),
            RelRequirement(
                first_station_id="a", second_station_id="c", level="X", reason="r", provenance="p"
            ),
            RelRequirement(
                first_station_id="b", second_station_id="c", level="O", reason="r", provenance="p"
            ),
        ]
    )
    assert set(evaluate_rel_closeness(matrix, [("a", "b"), ("a", "c")])) == {"O"}


def test_pareto_uses_all_dimensions_and_keeps_equal_points() -> None:
    points = [
        ParetoPoint("a", {"x": Fraction(2), "y": Fraction(1)}),
        ParetoPoint("b", {"x": Fraction(1), "y": Fraction(2)}),
        ParetoPoint("c", {"x": Fraction(1), "y": Fraction(1)}),
    ]
    classified = classify_pareto(points, {"x": "maximize", "y": "maximize"})
    assert classified["c"] == (True, ["a", "b"])
    assert classified["a"] == (False, [])
    assert classified["b"] == (False, [])


def test_v2_rejects_a_study_without_selected_criteria() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        DecisionModelV2,
    )

    with pytest.raises(ValueError, match="al menos un criterio"):
        DecisionModelV2()


def test_typed_evaluators_report_missing_invalid_and_undirected_evidence() -> None:
    missing = evaluate_retained_layouts(None, 6)
    assert missing.status == "inconclusive" and missing.fraction is None
    invalid = evaluate_retained_layouts(7, 6)
    assert invalid.status == "invalid" and invalid.fraction is None
    with pytest.raises(ValueError, match="denominador"):
        _fraction(0, 0)
    matrix = FlowMatrix(
        unit="piezas",
        horizon="hora",
        provenance="ERP",
        directed=False,
        entries=[FlowEntry(from_station_id="a", to_station_id="b", quantity=Decimal("4.5"))],
    )
    flow = evaluate_adjacency_flow(matrix, [("b", "a"), ("b", "a")])
    assert flow.total == Decimal("4.5")
    assert flow.contributions[0].reverse_quantity is None


def test_objective_catalog_rejects_unknown_and_snapshots_only_selected_dimensions() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        DecisionModelV2,
    )
    from tesis_domain_extensions.domains.single_row_facility_layout.objectives.catalog import (
        resolve_objective,
        selected_objective_snapshots,
    )
    from tesis_domain_extensions.errors import DomainExtensionError

    retained = DecisionModelV2(retained_compatible_layouts=True)
    assert [item.definition.id for item in selected_objective_snapshots(retained)] == [
        "retained-compatible-layouts"
    ]
    assert resolve_objective("rel-closeness").name == "Cobertura de prioridades de cercanía"
    assert "en qué niveles" in resolve_objective("rel-closeness").decision_question
    assert resolve_objective("retained-compatible-layouts").name == ("Flexibilidad de distribución")
    assert resolve_objective("captured-adjacency-flow").name == (
        "Valores de las adyacencias obligatorias"
    )
    with pytest.raises(DomainExtensionError, match="desconocido"):
        resolve_objective("missing")


def test_matrix_contracts_canonicalize_pairs_and_reject_duplicates() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.objectives.contracts import (
        UndesiredAdjacency,
    )

    reversed_rel = RelRequirement(
        first_station_id="b", second_station_id="a", level="A", reason="r", provenance="p"
    )
    assert (reversed_rel.first_station_id, reversed_rel.second_station_id) == ("a", "b")
    with pytest.raises(ValueError, match="reflexiva"):
        RelRequirement(
            first_station_id="a", second_station_id="a", level="A", reason="r", provenance="p"
        )
    with pytest.raises(ValueError, match="repetir pares"):
        RelMatrix(requirements=[reversed_rel, reversed_rel])
    reversed_flow = FlowMatrix(
        unit="u",
        horizon="h",
        provenance="p",
        directed=False,
        entries=[FlowEntry(from_station_id="b", to_station_id="a", quantity=Decimal("0"))],
    )
    assert (reversed_flow.entries[0].from_station_id, reversed_flow.entries[0].to_station_id) == (
        "a",
        "b",
    )
    reversed_value = AdjacencyValueMatrix(
        id="matrix-1",
        name="Matriz 1",
        description="Valor",
        direction="maximize",
        unit="puntos",
        provenance="prueba",
        directed=False,
        entries=[AdjacencyValueEntry(from_station_id="b", to_station_id="a", value=Decimal("1"))],
    )
    assert (
        reversed_value.entries[0].from_station_id,
        reversed_value.entries[0].to_station_id,
    ) == ("a", "b")
    with pytest.raises(ValueError, match="repetir celdas"):
        FlowMatrix(
            unit="u",
            horizon="h",
            provenance="p",
            directed=False,
            entries=[
                FlowEntry(from_station_id="a", to_station_id="b", quantity=Decimal("0")),
                FlowEntry(from_station_id="b", to_station_id="a", quantity=Decimal("1")),
            ],
        )
    with pytest.raises(ValueError, match="repetir celdas"):
        AdjacencyValueMatrix(
            id="matrix-1",
            name="Matriz 1",
            description="Valor",
            direction="maximize",
            unit="puntos",
            provenance="prueba",
            directed=False,
            entries=[
                AdjacencyValueEntry(from_station_id="a", to_station_id="b", value=Decimal("0")),
                AdjacencyValueEntry(from_station_id="b", to_station_id="a", value=Decimal("1")),
            ],
        )
    directed_flow = FlowMatrix(
        unit="u",
        horizon="h",
        provenance="p",
        directed=True,
        entries=[FlowEntry(from_station_id="b", to_station_id="a", quantity=Decimal("2"))],
    )
    assert (directed_flow.entries[0].from_station_id, directed_flow.entries[0].to_station_id) == (
        "b",
        "a",
    )
    reversed_policy = UndesiredAdjacency(
        first_station_id="b",
        second_station_id="a",
        cause="safety",
        explanation="e",
        provenance="p",
        policy="warn",
    )
    assert (reversed_policy.first_station_id, reversed_policy.second_station_id) == ("a", "b")
    with pytest.raises(ValueError, match="reflexiva"):
        UndesiredAdjacency(
            first_station_id="a",
            second_station_id="a",
            cause="safety",
            explanation="e",
            provenance="p",
            policy="warn",
        )


def test_v2_study_contract_rejects_ambiguous_catalog_entries() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        LayoutDesignV2,
        LayoutStudyV2,
        LinearComponentV2,
    )

    with pytest.raises(ValueError, match="repetir estaciones"):
        LinearComponentV2(id="c", station_ids=["a", "a"])
    with pytest.raises(ValueError, match="deben ser únicas"):
        LayoutDesignV2(id="d", title="D", base_component_ids=["c", "c"])
    with pytest.raises(ValueError, match="estaciones declaradas"):
        LayoutStudyV2(
            id="s",
            title="S",
            stations=[{"id": "a", "name": "A"}],
            components=[{"id": "c", "station_ids": ["a", "b"]}],
            designs=[{"id": "d", "title": "D", "base_component_ids": ["c"]}],
        )
    with pytest.raises(ValueError, match="duplicados"):
        LayoutStudyV2(
            id="s",
            title="S",
            stations=[{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
            components=[
                {"id": "c1", "station_ids": ["a", "b"]},
                {"id": "c2", "station_ids": ["b", "a"]},
            ],
            designs=[{"id": "d", "title": "D", "base_component_ids": ["c1"]}],
        )
    control = LayoutStudyV2(
        id="s",
        title="S",
        stations=[{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
        components=[{"id": "c", "station_ids": ["a", "b"]}],
        designs=[{"id": "control", "title": "Control", "base_component_ids": []}],
    )
    assert control.designs[0].base_component_ids == []
    with pytest.raises(ValueError, match="sólo puede existir un diseño de control"):
        LayoutStudyV2(
            id="s",
            title="S",
            stations=[{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
            components=[{"id": "c", "station_ids": ["a", "b"]}],
            designs=[
                {"id": "control-1", "title": "Control 1", "base_component_ids": []},
                {"id": "control-2", "title": "Control 2", "base_component_ids": []},
            ],
        )


def test_v2_pipeline_types_pareto_warnings_and_forbidden_partition() -> None:
    from tesis_domain_extensions.contracts.common import ProducerRef, large_non_negative_integer
    from tesis_domain_extensions.contracts.projection import domain_experiment_id
    from tesis_domain_extensions.contracts.results import RouteCount
    from tesis_domain_extensions.domains.single_row_facility_layout.adapter_v2 import (
        SingleRowFacilityLayoutAdapterV2,
    )
    from tesis_domain_extensions.domains.single_row_facility_layout.analysis_v2 import (
        build_result_v2,
    )
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
        LayoutForestResult,
    )
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        DomainRunManifestV2,
        GenerationMetricsV2,
        SingleRowFacilityLayoutConfigV2,
    )

    config = SingleRowFacilityLayoutConfigV2.model_validate(
        {
            "schema_version": "2.0.0",
            "domain": {"id": "single-row-facility-layout", "version": "2.0.0"},
            "study": {
                "id": "typed-v2",
                "title": "Typed v2",
                "stations": [{"id": item, "name": item.upper()} for item in "abc"],
                "components": [
                    {"id": "base", "station_ids": ["a", "b"]},
                    {"id": "warn", "station_ids": ["b", "c"]},
                    {"id": "forbidden", "station_ids": ["a", "c"]},
                ],
                "designs": [{"id": "d1", "title": "D1", "base_component_ids": ["base"]}],
            },
            "decision_model": {
                "retained_compatible_layouts": True,
                "rel_closeness": {
                    "requirements": [
                        {
                            "first_station_id": "a",
                            "second_station_id": "b",
                            "level": "A",
                            "reason": "r",
                            "provenance": "p",
                        },
                        {
                            "first_station_id": "a",
                            "second_station_id": "c",
                            "level": "X",
                            "reason": "r",
                            "provenance": "p",
                        },
                        {
                            "first_station_id": "b",
                            "second_station_id": "c",
                            "level": "X",
                            "reason": "r",
                            "provenance": "p",
                        },
                    ]
                },
                "adjacency_flow": {
                    "unit": "piezas",
                    "horizon": "hora",
                    "provenance": "ERP",
                    "directed": True,
                    "entries": [
                        {"from_station_id": "a", "to_station_id": "b", "quantity": Decimal("70")},
                        {"from_station_id": "b", "to_station_id": "a", "quantity": Decimal("50")},
                        {"from_station_id": "a", "to_station_id": "c", "quantity": Decimal("0")},
                        {"from_station_id": "c", "to_station_id": "a", "quantity": Decimal("0")},
                        {"from_station_id": "b", "to_station_id": "c", "quantity": Decimal("30")},
                        {"from_station_id": "c", "to_station_id": "b", "quantity": Decimal("0")},
                    ],
                },
                "undesired_prescribed_adjacencies": [
                    {
                        "first_station_id": "a",
                        "second_station_id": "c",
                        "cause": "safety",
                        "explanation": "Separar",
                        "provenance": "norma",
                        "policy": "forbidden",
                    },
                    {
                        "first_station_id": "b",
                        "second_station_id": "c",
                        "cause": "process",
                        "explanation": "Revisar",
                        "provenance": "equipo",
                        "policy": "warn",
                    },
                ],
            },
            "execution": _execution(),
            "reporting": {"invalid_combinations": "full"},
        }
    )
    adapter = SingleRowFacilityLayoutAdapterV2()
    context = adapter.project(config).context
    generation = adapter.generate_cases(config, context)
    cases = list(generation.cases)
    assert len(cases) == 2
    assert generation.statistics.forbidden_combinations == 2

    def count(edges: list[tuple[str, str]]) -> int:
        required = {tuple(sorted(edge)) for edge in edges}
        return sum(
            required <= {tuple(sorted((order[index], order[index + 1]))) for index in range(2)}
            for order in permutations("abc")
            if order <= tuple(reversed(order))
        )

    evidence = [
        LayoutForestResult(
            forest_id=case.case_id,
            origins=[case.origin],
            edges=case.payload.edges,
            core_run_id="11111111-1111-4111-8111-111111111111",
            feasibility="feasible",
            compatible_layout_count=RouteCount(
                value=large_non_negative_integer(count(case.payload.edges)),
                method=ProducerRef(id="test", version="1"),
                exact_value=None,
                reference_value=None,
                counting_convention="undirected_paths_reverse_identified",
                comparison_status="not_applicable",
            ),
            technical_metrics=None,
            diagnostics=[],
            limitations=[],
        )
        for case in cases
    ]
    experiment_id = domain_experiment_id(config)
    manifest = DomainRunManifestV2(
        schema_version="2.0.0",
        domain_run_id="22222222-2222-4222-8222-222222222222",
        domain_experiment_id=experiment_id,
        domain=config.domain,
        display_name=config.study.title,
        status="completed",
        generator_cursor=2,
        generation=GenerationMetricsV2(
            theoretical_combinations=4,
            cycle_pruned_branches=0,
            degree_pruned_branches=0,
            valid_selections=2,
            invalid_combinations=2,
            structural_invalid_combinations=0,
            forbidden_combinations=2,
            duplicate_forests=0,
            core_cases=2,
        ),
        cases=[],
        created_at="2026-09-16T00:00:00.000Z",
        updated_at="2026-09-16T00:00:00.000Z",
    )
    result = build_result_v2(config, context, manifest, evidence)
    design = result.designs[0]
    assert design.valid_case_count == 2 and design.invalid_combination_count == 2
    assert all(case.pareto_classification.status == "conclusive" for case in design.cases)
    assert set(design.pareto_case_ids) == {case.case_id for case in design.cases}
    warned = next(case for case in design.cases if case.findings)
    assert warned.captured_flow is not None and warned.captured_flow.total == Decimal("150")
    assert warned.findings[0].policy == "warn"
    assert {snapshot.definition.id for snapshot in result.objective_snapshots} == {
        "retained-compatible-layouts",
        "rel-closeness-a",
        "captured-adjacency-flow",
    }
    from tesis_domain_extensions.domains.single_row_facility_layout.analysis_v2 import (
        _differences,
    )

    base = next(case for case in design.cases if not case.added_component_ids)
    same_flow = warned.model_copy(
        update={"captured_flow": warned.captured_flow.model_copy(update={"total": Decimal("120")})}
    )
    differences = _differences(
        same_flow,
        [base.case_id],
        {base.case_id: base, same_flow.case_id: same_flow},
        {
            "retained-compatible-layouts": "maximize",
            "rel-closeness-a": "maximize",
            "captured-adjacency-flow": "maximize",
        },
    )
    assert [item.objective_id for item in differences] == ["retained-compatible-layouts"]


def test_v2_requires_exactly_one_policy_for_every_rel_x() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        SingleRowFacilityLayoutConfigV2,
    )

    payload = {
        "schema_version": "2.0.0",
        "domain": {"id": "single-row-facility-layout", "version": "2.0.0"},
        "study": {
            "id": "x-policy",
            "title": "X",
            "stations": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
            "components": [{"id": "c", "station_ids": ["a", "b"]}],
            "designs": [{"id": "d", "title": "D", "base_component_ids": ["c"]}],
        },
        "decision_model": {
            "rel_closeness": {
                "requirements": [
                    {
                        "first_station_id": "a",
                        "second_station_id": "b",
                        "level": "X",
                        "reason": "r",
                        "provenance": "p",
                    }
                ]
            },
            "undesired_prescribed_adjacencies": [],
        },
        "execution": _execution(),
        "reporting": {"invalid_combinations": "summary"},
    }
    with pytest.raises(ValueError, match="exactamente una política"):
        SingleRowFacilityLayoutConfigV2.model_validate(payload)


def test_v2_accepts_decimal_strings_declared_by_its_json_schema() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        SingleRowFacilityLayoutConfigV2,
    )

    payload = {
        "schema_version": "2.0.0",
        "domain": {"id": "single-row-facility-layout", "version": "2.0.0"},
        "study": {
            "id": "decimal-flow",
            "title": "Decimal flow",
            "stations": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
            "components": [{"id": "c", "station_ids": ["a", "b"]}],
            "designs": [{"id": "d", "title": "D", "base_component_ids": ["c"]}],
        },
        "decision_model": {
            "selected_objectives": [{"id": "captured-adjacency-flow", "version": "1"}],
            "adjacency_flow": {
                "unit": "viajes",
                "horizon": "día",
                "provenance": "medición",
                "directed": True,
                "entries": [
                    {
                        "from_station_id": "a",
                        "to_station_id": "b",
                        "quantity": "17.5",
                    },
                    {
                        "from_station_id": "b",
                        "to_station_id": "a",
                        "quantity": "0",
                    },
                ],
            },
        },
        "execution": _execution(),
        "reporting": {"invalid_combinations": "summary"},
    }
    config = SingleRowFacilityLayoutConfigV2.model_validate_json(json.dumps(payload))
    assert config.decision_model.adjacency_flow is not None
    assert config.decision_model.adjacency_flow.entries[0].quantity == Decimal("17.5")


def test_v2_rejects_rel_objectives_that_can_only_remain_zero() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        SingleRowFacilityLayoutConfigV2,
    )

    payload = {
        "schema_version": "2.0.0",
        "domain": {"id": "single-row-facility-layout", "version": "2.0.0"},
        "study": {
            "id": "rel-without-candidates",
            "title": "REL without candidates",
            "stations": [{"id": item, "name": item.upper()} for item in "abc"],
            "components": [{"id": "a-b", "station_ids": ["a", "b"]}],
            "designs": [{"id": "d", "title": "D", "base_component_ids": ["a-b"]}],
        },
        "decision_model": {
            "rel_closeness": {
                "requirements": [
                    {
                        "first_station_id": "a",
                        "second_station_id": "b",
                        "level": "U",
                        "reason": "r",
                        "provenance": "p",
                    },
                    {
                        "first_station_id": "a",
                        "second_station_id": "c",
                        "level": "A",
                        "reason": "r",
                        "provenance": "p",
                    },
                    {
                        "first_station_id": "b",
                        "second_station_id": "c",
                        "level": "U",
                        "reason": "r",
                        "provenance": "p",
                    },
                ]
            }
        },
        "execution": _execution(),
    }
    with pytest.raises(ValueError, match="nivel REL A no tiene ninguna restricción candidata"):
        SingleRowFacilityLayoutConfigV2.model_validate(payload)


def test_v2_reads_existing_projection_created_before_actionability_rule(
    tmp_path: Path,
) -> None:
    from tesis_domain_extensions.contracts.projection import domain_experiment_id
    from tesis_domain_extensions.domains.single_row_facility_layout.adapter_v2 import (
        SingleRowFacilityLayoutAdapterV2,
    )
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        SingleRowFacilityLayoutConfigV2,
    )

    payload = {
        "schema_version": "2.0.0",
        "domain": {"id": "single-row-facility-layout", "version": "2.0.0"},
        "study": {
            "id": "historical-rel-without-candidates",
            "title": "Historical REL without candidates",
            "stations": [{"id": item, "name": item.upper()} for item in "abc"],
            "components": [{"id": "a-b", "station_ids": ["a", "b"]}],
            "designs": [{"id": "d", "title": "D", "base_component_ids": ["a-b"]}],
        },
        "decision_model": {
            "rel_closeness": {
                "requirements": [
                    {
                        "first_station_id": "a",
                        "second_station_id": "b",
                        "level": "U",
                        "reason": "r",
                        "provenance": "p",
                    },
                    {
                        "first_station_id": "a",
                        "second_station_id": "c",
                        "level": "A",
                        "reason": "r",
                        "provenance": "p",
                    },
                    {
                        "first_station_id": "b",
                        "second_station_id": "c",
                        "level": "U",
                        "reason": "r",
                        "provenance": "p",
                    },
                ]
            }
        },
        "execution": _execution(),
    }
    with pytest.raises(ValueError, match="nivel REL A no tiene ninguna restricción candidata"):
        SingleRowFacilityLayoutConfigV2.model_validate(payload)

    historical_config = SingleRowFacilityLayoutConfigV2.model_validate(
        payload,
        context={"historical_projection": True},
    )
    adapter = SingleRowFacilityLayoutAdapterV2()
    context = adapter.project(historical_config).context
    from tesis_domain_extensions.domains.single_row_facility_layout.objectives.catalog import (
        selected_objective_snapshots,
    )

    experiment_id = domain_experiment_id(historical_config)
    record = {
        "schema_version": "2.0.0",
        "domain_experiment_id": experiment_id,
        "created_at": "2026-09-18T12:00:00.000Z",
        "domain_config": historical_config.model_dump(mode="json"),
        "projection_context": context.model_dump(mode="json"),
        "objective_snapshots": [
            item.model_dump(mode="json")
            for item in selected_objective_snapshots(historical_config.decision_model)
        ],
    }

    loaded = adapter.parse_projection_record(json.dumps(record).encode("utf-8"))
    assert loaded.domain_experiment_id == experiment_id
    assert loaded.domain_config.study.id == "historical-rel-without-candidates"

    from tesis_domain_extensions.projection_store import ProjectionStore
    from tesis_proyect.application.commands import CoreCommands

    (tmp_path / "experiments").mkdir()
    (tmp_path / "runs").mkdir()
    projections = tmp_path / "domain_projections"
    projections.mkdir()
    (projections / f"{experiment_id}.json").write_text(
        json.dumps(record),
        encoding="utf-8",
    )
    stored = ProjectionStore(tmp_path, CoreCommands.open(tmp_path)).load(experiment_id)
    assert stored.record.domain_config.study.id == "historical-rel-without-candidates"


def test_v2_rejects_flow_objectives_without_positive_candidate_edges() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        SingleRowFacilityLayoutConfigV2,
    )

    payload = {
        "schema_version": "2.0.0",
        "domain": {"id": "single-row-facility-layout", "version": "2.0.0"},
        "study": {
            "id": "flow-without-candidates",
            "title": "Flow without candidates",
            "stations": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
            "components": [{"id": "a-b", "station_ids": ["a", "b"]}],
            "designs": [{"id": "d", "title": "D", "base_component_ids": ["a-b"]}],
        },
        "decision_model": {
            "adjacency_flow": {
                "unit": "viajes",
                "horizon": "día",
                "provenance": "medición",
                "directed": False,
                "entries": [{"from_station_id": "a", "to_station_id": "b", "quantity": "0"}],
            }
        },
        "execution": _execution(),
    }
    with pytest.raises(ValueError, match="no tiene restricciones candidatas con movimientos"):
        SingleRowFacilityLayoutConfigV2.model_validate(payload)


def _adjacency_matrix_payload(
    identifier: str, name: str, direction: str, values: tuple[str, str] = ("1.25", "2.75")
) -> dict[str, object]:
    return {
        "id": identifier,
        "name": name,
        "description": f"Qué representa {name}",
        "direction": direction,
        "unit": "puntos",
        "reference_period": "mes",
        "provenance": "sistema fuente",
        "directed": True,
        "entries": [
            {"from_station_id": "a", "to_station_id": "b", "value": values[0]},
            {"from_station_id": "b", "to_station_id": "a", "value": values[1]},
        ],
    }


def _multiple_matrix_config() -> dict[str, object]:
    return {
        "schema_version": "2.0.0",
        "domain": {"id": "single-row-facility-layout", "version": "2.0.0"},
        "study": {
            "id": "multi-matrix",
            "title": "Multiple matrix",
            "stations": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
            "components": [{"id": "a-b", "station_ids": ["a", "b"]}],
            "designs": [{"id": "d", "title": "D", "base_component_ids": ["a-b"]}],
        },
        "decision_model": {
            "selected_objectives": [{"id": "captured-adjacency-flow", "version": "1"}],
            "adjacency_flow": [
                _adjacency_matrix_payload("beneficio", "Beneficio", "maximize"),
                _adjacency_matrix_payload("costo", "Costo", "minimize", ("3.10", "4.20")),
            ],
        },
        "execution": _execution(),
    }


@pytest.mark.parametrize("version", ["2.0.0", "2.1.0"])
@pytest.mark.parametrize("direction", ["maximize", "minimize"])
def test_negative_pareto_differences_keep_exact_decimal_values(
    tmp_path: Path, version: str, direction: str
) -> None:
    from tesis_domain_extensions.application import DomainApplication
    from tesis_proyect.application.commands import CoreCommands

    payload = _multiple_matrix_config()
    payload["schema_version"] = version
    payload["domain"]["version"] = version  # type: ignore[index]
    payload["study"]["stations"].append({"id": "c", "name": "C"})  # type: ignore[index,union-attr]
    payload["study"]["components"].append({"id": "b-c", "station_ids": ["b", "c"]})  # type: ignore[index,union-attr]
    matrix = _adjacency_matrix_payload("cost", "Cost", direction, ("-0.0000001", "0"))
    matrix["entries"].extend(
        [  # type: ignore[union-attr]
            {"from_station_id": a, "to_station_id": b, "value": "-0.0000001"}
            for a, b in [("a", "c"), ("c", "a"), ("b", "c"), ("c", "b")]
        ]
    )
    payload["decision_model"]["adjacency_flow"] = [matrix]  # type: ignore[index]
    application = DomainApplication(tmp_path, CoreCommands.open(tmp_path))
    prepared = application.prepare_payload(json.dumps(payload).encode())
    result = application.run(prepared.domain_experiment_id).result
    differences = [
        difference
        for design in result.designs
        for item in design.cases  # type: ignore[attr-defined]
        for difference in item.pareto_classification.differences
    ]
    assert differences
    for difference in differences:
        assert isinstance(difference.preferred_value, str)
        assert isinstance(difference.other_value, str)
        assert "E" not in difference.preferred_value and "/" not in difference.preferred_value
        left, right = Decimal(difference.preferred_value), Decimal(difference.other_value)
        assert (left > right) if direction == "maximize" else (left < right)
    from tesis_domain_extensions.domains.single_row_facility_layout.analysis_v2 import _differences

    negative = result.designs[0].cases[0]  # type: ignore[attr-defined]
    zero = negative.model_copy(
        update={
            "case_id": "0" * 64,
            "adjacency_values": [
                negative.adjacency_values[0].model_copy(update={"total": Decimal("0")})
            ],
        }
    )
    preferred, other = (zero, negative) if direction == "maximize" else (negative, zero)
    mixed = _differences(
        other, [preferred.case_id], {preferred.case_id: preferred}, {"adjacency-cost": direction}
    )
    assert len(mixed) == 1
    zero_value = mixed[0].preferred_value if direction == "maximize" else mixed[0].other_value
    assert not isinstance(zero_value, str) and zero_value.numerator == 0
    application.close()


def test_v2_normalizes_a_reversed_complete_undirected_matrix() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        SingleRowFacilityLayoutConfigV2,
    )

    payload = _multiple_matrix_config()
    matrix = _adjacency_matrix_payload("beneficio", "Beneficio", "maximize")
    matrix["directed"] = False
    matrix["entries"] = [{"from_station_id": "b", "to_station_id": "a", "value": "12.5"}]
    payload["decision_model"]["adjacency_flow"] = [matrix]  # type: ignore[index]
    config = SingleRowFacilityLayoutConfigV2.model_validate(payload)
    assert isinstance(config.decision_model.adjacency_flow, list)
    entry = config.decision_model.adjacency_flow[0].entries[0]
    assert (entry.from_station_id, entry.to_station_id, entry.value) == (
        "a",
        "b",
        Decimal("12.5"),
    )


def test_multiple_adjacency_matrices_keep_exact_totals_and_directions() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        SingleRowFacilityLayoutConfigV2,
    )
    from tesis_domain_extensions.domains.single_row_facility_layout.objectives.catalog import (
        selected_objective_snapshots,
    )

    config = SingleRowFacilityLayoutConfigV2.model_validate(_multiple_matrix_config())
    assert isinstance(config.decision_model.adjacency_flow, list)
    results = [
        evaluate_adjacency_value(matrix, [("b", "a")])
        for matrix in config.decision_model.adjacency_flow
    ]
    assert [result.total for result in results] == [Decimal("4.00"), Decimal("7.30")]
    assert [result.objective_id for result in results] == ["adjacency-beneficio", "adjacency-costo"]
    assert [result.direction for result in results] == ["maximize", "minimize"]
    snapshots = selected_objective_snapshots(config.decision_model)
    assert [(item.definition.id, item.definition.direction) for item in snapshots] == [
        ("adjacency-beneficio", "maximize"),
        ("adjacency-costo", "minimize"),
    ]


def test_v2_accepts_signed_and_zero_quantitative_matrices() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        SingleRowFacilityLayoutConfigV2,
    )

    payload = _multiple_matrix_config()
    for matrix, value in zip(
        payload["decision_model"]["adjacency_flow"], ["-4.25", "0"], strict=True
    ):  # type: ignore[index]
        for entry in matrix["entries"]:  # type: ignore[index]
            entry["value"] = value
    config = SingleRowFacilityLayoutConfigV2.model_validate(payload)
    assert isinstance(config.decision_model.adjacency_flow, list)
    assert [
        evaluate_adjacency_value(matrix, [("a", "b")]).total
        for matrix in config.decision_model.adjacency_flow
    ] == [Decimal("-8.50"), Decimal("0")]


def test_v2_accepts_rel_with_only_u_and_x_without_priority_dimensions() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        SingleRowFacilityLayoutConfigV2,
    )
    from tesis_domain_extensions.domains.single_row_facility_layout.objectives.catalog import (
        selected_objective_snapshots,
    )

    payload = _multiple_matrix_config()
    payload["study"]["stations"].append({"id": "c", "name": "C"})  # type: ignore[index]
    payload["decision_model"] = {  # type: ignore[index]
        "selected_objectives": [{"id": "rel-closeness", "version": "1"}],
        "rel_closeness": {
            "requirements": [
                {
                    "first_station_id": a,
                    "second_station_id": b,
                    "level": level,
                    "reason": "r",
                    "provenance": "p",
                }
                for a, b, level in [("a", "b", "U"), ("a", "c", "X"), ("b", "c", "U")]
            ]
        },
        "undesired_prescribed_adjacencies": [
            {
                "first_station_id": "a",
                "second_station_id": "c",
                "cause": "safety",
                "explanation": "Separar",
                "provenance": "norma",
                "policy": "forbidden",
            }
        ],
    }
    config = SingleRowFacilityLayoutConfigV2.model_validate(payload)
    assert selected_objective_snapshots(config.decision_model) == []


def test_v2_active_duration_excludes_cancelled_and_interrupted_gaps() -> None:
    from types import SimpleNamespace

    from tesis_domain_extensions.application import DomainApplication
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        DomainRunManifestV2,
    )

    timestamps = iter(
        [
            "2026-09-29T00:00:01.000Z",
            "2026-09-29T00:00:04.000Z",
            "2026-09-29T00:01:00.000Z",
            "2026-09-29T00:01:02.000Z",
            "2026-09-29T00:02:00.000Z",
            "2026-09-29T00:02:03.000Z",
        ]
    )
    app = object.__new__(DomainApplication)
    app.store = SimpleNamespace(clock=lambda: next(timestamps))  # type: ignore[assignment]
    adapter = SimpleNamespace(domain_run_model=DomainRunManifestV2)
    manifest = DomainRunManifestV2.model_validate(
        {
            "schema_version": "2.0.0",
            "domain_run_id": "22222222-2222-4222-8222-222222222222",
            "domain_experiment_id": "a" * 64,
            "domain": {"id": "single-row-facility-layout", "version": "2.0.0"},
            "display_name": "Prueba",
            "status": "created",
            "generator_cursor": 0,
            "cases": [],
            "generation": {
                key: 0
                for key in [
                    "theoretical_combinations",
                    "cycle_pruned_branches",
                    "degree_pruned_branches",
                    "valid_selections",
                    "invalid_combinations",
                    "structural_invalid_combinations",
                    "forbidden_combinations",
                    "duplicate_forests",
                    "core_cases",
                ]
            },
            "created_at": "2026-09-29T00:00:00.000Z",
            "updated_at": "2026-09-29T00:00:00.000Z",
        }
    )
    manifest = app._update_group_manifest(
        adapter, manifest, status="running", new_active_segment=True
    )
    manifest = app._update_group_manifest(adapter, manifest, status="cancelled")
    assert manifest.active_duration_ms == 3000
    manifest = app._update_group_manifest(
        adapter, manifest, status="running", new_active_segment=True
    )
    manifest = app._update_group_manifest(adapter, manifest)
    manifest = app._update_group_manifest(
        adapter, manifest, status="running", new_active_segment=True
    )
    manifest = app._update_group_manifest(adapter, manifest, status="completed")
    assert manifest.active_duration_ms == 8000
    assert manifest.active_started_at is None


def test_adjacency_matrix_contract_rejects_float_duplicates_and_incomplete_data() -> None:
    from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
        SingleRowFacilityLayoutConfigV2,
    )

    with pytest.raises(ValueError, match="decimal exacto"):
        AdjacencyValueEntry(from_station_id="a", to_station_id="b", value=1.2)
    payload = _multiple_matrix_config()
    matrices = payload["decision_model"]["adjacency_flow"]  # type: ignore[index]
    matrices[1]["id"] = "beneficio"  # type: ignore[index]
    with pytest.raises(ValueError, match="identificadores de matrices"):
        SingleRowFacilityLayoutConfigV2.model_validate(payload)
    incomplete = _multiple_matrix_config()
    incomplete["decision_model"]["adjacency_flow"][0]["entries"].pop()  # type: ignore[index]
    with pytest.raises(ValueError, match="completa y explícita"):
        SingleRowFacilityLayoutConfigV2.model_validate(incomplete)


def test_pareto_supports_mixed_maximize_and_minimize_dimensions() -> None:
    points = [
        ParetoPoint("a", {"benefit": Fraction(8), "cost": Fraction(3)}),
        ParetoPoint("b", {"benefit": Fraction(7), "cost": Fraction(5)}),
        ParetoPoint("c", {"benefit": Fraction(9), "cost": Fraction(8)}),
    ]
    classified = classify_pareto(points, {"benefit": "maximize", "cost": "minimize"})
    assert classified["b"] == (True, ["a"])
    assert classified["a"] == (False, [])
    assert classified["c"] == (False, [])
