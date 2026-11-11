from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import Any, Literal, cast

from tesis_domain_extensions.contracts.common import large_non_negative_integer
from tesis_domain_extensions.contracts.results import DomainLimitation, ExactFraction
from tesis_domain_extensions.domains.single_row_facility_layout.analysis import (
    _forest_structure,
    decision_case_id,
)
from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
    LayoutForestResult,
)
from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
    DomainRunManifestV2,
    InvalidCombinationSummaryV2,
    LayoutCaseResultV2,
    LayoutDesignResultV2,
    SingleRowFacilityLayoutConfigV2,
    SingleRowFacilityLayoutResultV2,
    SingleRowProjectionContextV2,
)
from tesis_domain_extensions.domains.single_row_facility_layout.generation import (
    LinearForestGenerator,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.catalog import (
    selected_objective_snapshots,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.contracts import (
    AdjacencyFinding,
    AdjacencyValueMatrix,
    ParetoClassification,
    ParetoDifference,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.evaluators import (
    evaluate_adjacency_flow,
    evaluate_adjacency_value,
    evaluate_rel_closeness,
    evaluate_retained_layouts,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.pareto import (
    ParetoPoint,
    classify_pareto,
)


def _exact(value: Fraction) -> ExactFraction:
    return ExactFraction(numerator=value.numerator, denominator=value.denominator)


def _difference_value(
    case: LayoutCaseResultV2, objective_id: str, value: Fraction
) -> ExactFraction | str:
    if value >= 0:
        return _exact(value)
    for observation in case.adjacency_values:
        if observation.objective_id == objective_id and observation.total is not None:
            return format(observation.total, "f")
    raise ValueError("Falta el valor decimal confirmado de la diferencia negativa.")


def _case_values(case: LayoutCaseResultV2) -> dict[str, Fraction]:
    values: dict[str, Fraction] = {}
    retained = case.retained_layouts
    if retained is not None and retained.status == "conclusive" and retained.fraction is not None:
        values[retained.objective_id] = Fraction(
            int(retained.fraction.numerator), int(retained.fraction.denominator)
        )
    for result in case.rel_closeness:
        if result.status == "conclusive":
            values[result.objective_id] = Fraction(
                int(result.fraction.numerator), int(result.fraction.denominator)
            )
    flow = case.captured_flow
    if flow is not None and flow.status == "conclusive" and flow.total is not None:
        values[flow.objective_id] = Fraction(Decimal(flow.total))
    for adjacency_result in case.adjacency_values:
        if adjacency_result.status == "conclusive" and adjacency_result.total is not None:
            values[adjacency_result.objective_id] = Fraction(Decimal(adjacency_result.total))
    return values


def _findings(
    config: SingleRowFacilityLayoutConfigV2, edges: list[tuple[str, str]]
) -> list[AdjacencyFinding]:
    prescribed = {tuple(sorted(edge)) for edge in edges}
    return [
        AdjacencyFinding(
            first_station_id=item.first_station_id,
            second_station_id=item.second_station_id,
            cause=item.cause,
            explanation=item.explanation,
            provenance=item.provenance,
            policy="warn",
        )
        for item in config.decision_model.undesired_prescribed_adjacencies
        if item.policy == "warn" and (item.first_station_id, item.second_station_id) in prescribed
    ]


def _differences(
    case: LayoutCaseResultV2,
    dominators: list[str],
    by_id: dict[str, LayoutCaseResultV2],
    directions: dict[str, Literal["maximize", "minimize"]],
) -> list[ParetoDifference]:
    case_values = _case_values(case)
    result: list[ParetoDifference] = []
    for dominator_id in dominators:
        preferred = _case_values(by_id[dominator_id])
        for objective_id, direction in directions.items():
            left, right = preferred[objective_id], case_values[objective_id]
            strictly_better = left > right if direction == "maximize" else left < right
            if strictly_better:
                result.append(
                    ParetoDifference(
                        objective_id=objective_id,
                        preferred_case_id=dominator_id,
                        preferred_value=_difference_value(by_id[dominator_id], objective_id, left),
                        other_case_id=case.case_id,
                        other_value=_difference_value(case, objective_id, right),
                    )
                )
    return result


def build_result_v2(
    config: SingleRowFacilityLayoutConfigV2,
    context: SingleRowProjectionContextV2,
    manifest: DomainRunManifestV2,
    forest_results: list[LayoutForestResult],
) -> SingleRowFacilityLayoutResultV2:
    if manifest.status not in {"completed", "failed", "cancelled"}:
        raise ValueError("la agregación requiere una ejecución terminal")
    generator = LinearForestGenerator(cast(Any, config), cast(Any, context))
    generated = list(generator)
    conflicts = generator.conflict_summaries()
    evidence = {item.forest_id: item for item in forest_results}
    components = {item.id: item for item in config.study.components}
    snapshots = selected_objective_snapshots(config.decision_model)
    active = [item.definition.id for item in snapshots]
    directions: dict[str, Literal["maximize", "minimize"]] = {
        item.definition.id: item.definition.direction for item in snapshots
    }
    policy_by_pair = {
        (item.first_station_id, item.second_station_id): item
        for item in config.decision_model.undesired_prescribed_adjacencies
    }
    designs: list[LayoutDesignResultV2] = []
    for design in config.study.designs:
        generated_design = [item for item in generated if item.origin.design_id == design.id]
        base_generated = next(
            (item for item in generated_design if not item.origin.added_component_ids), None
        )
        if base_generated is None:
            raise ValueError("falta el caso base del diseño")
        base_evidence = evidence.get(base_generated.forest_id)
        if base_evidence is None:
            raise ValueError("falta evidencia CORE para el caso base")
        base_raw = (
            None
            if base_evidence.compatible_layout_count is None
            else base_evidence.compatible_layout_count.value
        )
        base_count = int(base_raw) if base_raw is not None else None
        cases: list[LayoutCaseResultV2] = []
        for item in generated_design:
            found = evidence.get(item.forest_id)
            if found is None:
                raise ValueError("falta evidencia CORE para un bosque generado")
            added = list(item.origin.added_component_ids)
            count_raw = (
                None
                if found.compatible_layout_count is None
                else found.compatible_layout_count.value
            )
            count = int(count_raw) if count_raw is not None else None
            retained = (
                evaluate_retained_layouts(count, base_count)
                if config.decision_model.retained_compatible_layouts
                else None
            )
            rel = (
                list(
                    evaluate_rel_closeness(
                        config.decision_model.rel_closeness, found.edges
                    ).values()
                )
                if config.decision_model.rel_closeness is not None
                else []
            )
            flow_input = config.decision_model.adjacency_flow
            flow = (
                evaluate_adjacency_flow(flow_input, found.edges)
                if flow_input is not None and not isinstance(flow_input, list)
                else None
            )
            adjacency_values = (
                [
                    evaluate_adjacency_value(matrix, found.edges)
                    for matrix in flow_input
                    if isinstance(matrix, AdjacencyValueMatrix)
                ]
                if isinstance(flow_input, list)
                else []
            )
            cases.append(
                LayoutCaseResultV2(
                    case_id=decision_case_id(manifest.domain_experiment_id, design.id, added),
                    forest_id=found.forest_id,
                    design_id=design.id,
                    mandatory_component_ids=list(design.base_component_ids),
                    added_component_ids=added,
                    component_ids=[*design.base_component_ids, *added],
                    edges=found.edges,
                    forest_structure=_forest_structure(
                        [station.id for station in config.study.stations], found.edges
                    ),
                    prescribed_edge_count=len(found.edges),
                    core_run_id=found.core_run_id,
                    feasibility=found.feasibility,
                    compatible_layout_count=found.compatible_layout_count,
                    retained_layouts=retained,
                    rel_closeness=rel,
                    captured_flow=flow,
                    adjacency_values=adjacency_values,
                    findings=_findings(config, found.edges),
                    pareto_classification=ParetoClassification(
                        status="inconclusive",
                        objective_refs=active,
                        dominated=None,
                        pareto_optimal=None,
                    ),
                    technical_metrics=found.technical_metrics,
                    diagnostics=found.diagnostics,
                    limitations=found.limitations,
                )
            )
        feasible = [case for case in cases if case.feasibility == "feasible"]
        points = [ParetoPoint(case.case_id, _case_values(case)) for case in feasible]
        complete = bool(points) and all(set(point.values) == set(directions) for point in points)
        classification = classify_pareto(points, directions) if complete else {}
        by_id = {case.case_id: case for case in cases}
        finalized: list[LayoutCaseResultV2] = []
        for case in cases:
            conclusive = complete and case.case_id in classification
            dominated, dominators = classification.get(case.case_id, (False, []))
            finalized.append(
                case.model_copy(
                    update={
                        "pareto_classification": ParetoClassification(
                            status="conclusive" if conclusive else "inconclusive",
                            dominated=dominated if conclusive else None,
                            pareto_optimal=not dominated if conclusive else None,
                            dominated_by_case_ids=dominators,
                            objective_refs=active,
                            differences=(
                                _differences(case, dominators, by_id, directions)
                                if conclusive
                                else []
                            ),
                        )
                    }
                )
            )
        design_conflicts = [item for item in conflicts if item.design_id == design.id]
        invalid_count = sum(item.combination_count for item in design_conflicts)
        summaries: list[InvalidCombinationSummaryV2] = []
        for conflict_summary in design_conflicts:
            policy = next(
                (
                    policy_by_pair[edge]
                    for edge in conflict_summary.conflicting_edges
                    if edge in policy_by_pair
                ),
                None,
            )
            summaries.append(
                InvalidCombinationSummaryV2(
                    reason=conflict_summary.reason,
                    combination_count=large_non_negative_integer(
                        conflict_summary.combination_count
                    ),
                    affected_station_ids=list(conflict_summary.affected_station_ids),
                    conflicting_edges=list(conflict_summary.conflicting_edges),
                    conflicting_component_ids=list(conflict_summary.conflicting_component_ids),
                    cause=policy.cause if policy is not None else None,
                    explanation=policy.explanation if policy is not None else None,
                    provenance=policy.provenance if policy is not None else None,
                )
            )
        candidates = sorted(set(components) - set(design.base_component_ids))
        theoretical = 1 << len(candidates)
        if len(finalized) + invalid_count != theoretical:
            raise ValueError("la partición de combinaciones del diseño no es exhaustiva")
        pareto_ids = sorted(
            case.case_id for case in finalized if case.pareto_classification.pareto_optimal is True
        )
        designs.append(
            LayoutDesignResultV2(
                design_id=design.id,
                design_title=design.title,
                mandatory_component_ids=list(design.base_component_ids),
                candidate_component_ids=candidates,
                theoretical_combinations=large_non_negative_integer(theoretical),
                valid_case_count=large_non_negative_integer(len(finalized)),
                invalid_combination_count=large_non_negative_integer(invalid_count),
                invalid_combination_summaries=summaries,
                base_case_id=decision_case_id(manifest.domain_experiment_id, design.id, []),
                base_layout_count=base_evidence.compatible_layout_count,
                cases=sorted(finalized, key=lambda case: case.case_id),
                pareto_case_ids=pareto_ids,
            )
        )
    return SingleRowFacilityLayoutResultV2(
        schema_version="2.0.0",
        domain=config.domain,
        study_id=config.study.id,
        study_title=config.study.title,
        study_description=config.study.description,
        stations=list(config.study.stations),
        execution={
            "domain_run_id": manifest.domain_run_id,
            "domain_experiment_id": manifest.domain_experiment_id,
            "status": manifest.status,
        },
        generation=manifest.generation,
        objective_snapshots=snapshots,
        designs=designs,
        limitations=[
            DomainLimitation(
                code="DOMAIN_SCOPE", message="Los criterios no modelan distancia ni costo físico."
            )
        ],
    )
