from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Literal, cast

from tesis_domain_extensions.contracts.common import large_non_negative_integer
from tesis_domain_extensions.contracts.results import DomainLimitation
from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
    DomainExecutionRef,
    DomainRunManifest,
    InvalidCombination,
    InvalidConflictSummary,
    LayoutCaseResult,
    LayoutDesignResult,
    LayoutForestResult,
    LinearForestStructure,
    SingleRowFacilityLayoutConfig,
    SingleRowFacilityLayoutResult,
    SingleRowProjectionContext,
)
from tesis_domain_extensions.domains.single_row_facility_layout.generation import (
    GeneratedForest,
    LinearForestGenerator,
)
from tesis_domain_extensions.domains.single_row_facility_layout.interpretation import (
    PRIMARY_MEASURE,
)
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_domain_extensions.metrics import exact_fraction


def decision_case_id(
    domain_experiment_id: str,
    design_id: str,
    added_component_ids: list[str] | tuple[str, ...],
) -> str:
    payload = json.dumps(
        {
            "added_component_ids": sorted(added_component_ids),
            "design_id": design_id,
            "domain_experiment_id": domain_experiment_id,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _forest_structure(
    station_ids: list[str],
    edges: list[tuple[str, str]],
) -> LinearForestStructure:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for first, second in edges:
        adjacency[first].add(second)
        adjacency[second].add(first)
    remaining = set(adjacency)
    paths: list[list[str]] = []
    while remaining:
        component: set[str] = set()
        pending = [min(remaining)]
        while pending:
            station = pending.pop()
            if station in component:
                continue
            component.add(station)
            pending.extend(adjacency[station] - component)
        endpoints = sorted(item for item in component if len(adjacency[item]) == 1)
        current = endpoints[0]
        previous: str | None = None
        ordered = [current]
        while True:
            following = sorted(adjacency[current] - ({previous} if previous else set()))
            following = [item for item in following if item not in ordered]
            if not following:
                break
            previous, current = current, following[0]
            ordered.append(current)
        reverse = list(reversed(ordered))
        paths.append(min(ordered, reverse))
        remaining.difference_update(component)
    return LinearForestStructure(
        paths=sorted(paths),
        isolated_station_ids=sorted(set(station_ids) - set(adjacency)),
    )


def _classify(cases: list[LayoutCaseResult]) -> tuple[list[LayoutCaseResult], list[str]]:
    values = [_count_value_from_case(case) for case in cases]
    if any(value is None for value in values):
        return cases, []
    classified: list[LayoutCaseResult] = []
    pareto_ids: list[str] = []
    for index, case in enumerate(cases):
        count = values[index]
        assert count is not None
        utility = int(case.utility)
        dominated = any(
            other_index != index
            and int(other.utility) >= utility
            and other_count is not None
            and other_count >= count
            and (int(other.utility) > utility or other_count > count)
            for other_index, (other, other_count) in enumerate(zip(cases, values, strict=True))
        )
        current = case.model_copy(update={"dominated": dominated, "pareto_optimal": not dominated})
        classified.append(current)
        if not dominated:
            pareto_ids.append(case.case_id)
    return classified, sorted(pareto_ids)


def _count_value_from_case(case: LayoutCaseResult) -> int | None:
    count = case.compatible_layout_count
    if count is None or count.value is None:
        return None
    return int(count.value)


def build_result(  # noqa: C901 - design evidence and decision analysis remain cohesive
    config: SingleRowFacilityLayoutConfig,
    context: SingleRowProjectionContext,
    manifest: DomainRunManifest,
    forest_results: list[LayoutForestResult],
) -> SingleRowFacilityLayoutResult:
    if manifest.status not in {"completed", "failed", "cancelled"}:
        raise DomainExtensionError("La agregación requiere una ejecución terminal.")
    execution_status = cast(Literal["completed", "failed", "cancelled"], manifest.status)
    domain_experiment_id = manifest.domain_experiment_id
    generator = LinearForestGenerator(config, context)
    generated = list(generator)
    forest_evidence = {item.forest_id: item for item in forest_results}
    components = {item.id: item for item in config.study.components}
    station_ids = [item.id for item in config.study.stations]
    generated_by_design: dict[str, list[GeneratedForest]] = defaultdict(list)
    for item in generated:
        generated_by_design[item.origin.design_id].append(item)
    summaries = generator.conflict_summaries()
    design_results: list[LayoutDesignResult] = []
    for design in config.study.designs:
        candidates = sorted(set(components) - set(design.base_component_ids))
        preliminary: list[LayoutCaseResult] = []
        base_case_id = decision_case_id(domain_experiment_id, design.id, [])
        base_count = None
        for generated_case in generated_by_design[design.id]:
            evidence = forest_evidence.get(generated_case.forest_id)
            if evidence is None:
                raise DomainExtensionError("Falta evidencia CORE para un bosque generado.")
            added = list(generated_case.origin.added_component_ids)
            case_id = decision_case_id(domain_experiment_id, design.id, added)
            component_ids = [*design.base_component_ids, *added]
            utility = sum(components[item].utility for item in added)
            total_utility = sum(components[item].utility for item in component_ids)
            case = LayoutCaseResult(
                case_id=case_id,
                forest_id=evidence.forest_id,
                design_id=design.id,
                mandatory_component_ids=design.base_component_ids,
                added_component_ids=added,
                component_ids=component_ids,
                edges=evidence.edges,
                forest_structure=_forest_structure(station_ids, evidence.edges),
                prescribed_edge_count=len(evidence.edges),
                utility=large_non_negative_integer(utility),
                total_utility=large_non_negative_integer(total_utility),
                core_run_id=evidence.core_run_id,
                feasibility=evidence.feasibility,
                compatible_layout_count=evidence.compatible_layout_count,
                availability_ratio=None,
                restrictiveness_ratio=None,
                technical_metrics=evidence.technical_metrics,
                diagnostics=evidence.diagnostics,
                limitations=evidence.limitations,
                dominated=None,
                pareto_optimal=None,
            )
            if not added:
                base_count = evidence.compatible_layout_count
            preliminary.append(case)
        base_value = (
            None if base_count is None or base_count.value is None else int(base_count.value)
        )
        all_conclusive = base_value is not None and all(
            _count_value_from_case(case) is not None for case in preliminary
        )
        with_ratios: list[LayoutCaseResult] = []
        for case in preliminary:
            count = _count_value_from_case(case)
            if all_conclusive and count is not None and base_value is not None:
                if count > base_value:
                    raise DomainExtensionError(
                        "El CORE informó más layouts para un caso que para su diseño base."
                    )
                case = case.model_copy(
                    update={
                        "availability_ratio": exact_fraction(count, base_value),
                        "restrictiveness_ratio": exact_fraction(base_value - count, base_value),
                    }
                )
            with_ratios.append(case)
        classified, pareto_ids = _classify(with_ratios) if all_conclusive else (with_ratios, [])
        conflict_rows = [item for item in summaries if item.design_id == design.id]
        invalid_count = sum(item.combination_count for item in conflict_rows)
        invalid_details = None
        if config.reporting.invalid_combinations == "full":
            invalid_details = [
                InvalidCombination(
                    case_id=decision_case_id(
                        domain_experiment_id,
                        item.design_id,
                        item.added_component_ids,
                    ),
                    design_id=item.design_id,
                    added_component_ids=list(item.added_component_ids),
                    reason=cast(Literal["cycle", "degree_exceeded"], item.reason),
                    affected_station_ids=list(item.affected_station_ids),
                    conflicting_edges=list(item.conflicting_edges),
                    conflicting_component_ids=list(item.conflicting_component_ids),
                )
                for item in generator.invalid_combinations
                if item.design_id == design.id
            ]
            invalid_details.sort(key=lambda item: item.added_component_ids)
        valid_count = len(classified)
        theoretical = 1 << len(candidates)
        if valid_count + invalid_count != theoretical:
            raise DomainExtensionError("La partición de combinaciones del diseño es incoherente.")
        design_results.append(
            LayoutDesignResult(
                design_id=design.id,
                design_title=design.title,
                mandatory_component_ids=design.base_component_ids,
                candidate_component_ids=candidates,
                theoretical_combinations=large_non_negative_integer(theoretical),
                valid_case_count=large_non_negative_integer(valid_count),
                invalid_combination_count=large_non_negative_integer(invalid_count),
                base_case_id=base_case_id,
                base_layout_count=base_count,
                cases=sorted(classified, key=lambda item: item.case_id),
                invalid_conflicts=[
                    InvalidConflictSummary(
                        reason=cast(Literal["cycle", "degree_exceeded"], item.reason),
                        affected_station_ids=list(item.affected_station_ids),
                        conflicting_edges=list(item.conflicting_edges),
                        conflicting_component_ids=list(item.conflicting_component_ids),
                        combination_count=large_non_negative_integer(item.combination_count),
                    )
                    for item in conflict_rows
                ],
                invalid_combinations=invalid_details,
                pareto_case_ids=pareto_ids,
            )
        )
    return SingleRowFacilityLayoutResult(
        schema_version="1.0.0",
        domain=config.domain,
        study_id=config.study.id,
        study_title=config.study.title,
        study_description=config.study.description,
        stations=config.study.stations,
        execution=DomainExecutionRef(
            domain_run_id=manifest.domain_run_id,
            domain_experiment_id=domain_experiment_id,
            status=execution_status,
        ),
        primary_measure=PRIMARY_MEASURE,
        generation=manifest.generation,
        designs=design_results,
        limitations=[
            DomainLimitation(
                code="DOMAIN_SCOPE",
                message=(
                    "El análisis compara requisitos de adyacencia y no recomienda un layout "
                    "arquitectónico o industrial definitivo."
                ),
            )
        ],
    )
