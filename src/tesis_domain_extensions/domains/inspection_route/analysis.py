from __future__ import annotations

from typing import Literal, cast

from tesis_domain_extensions.contracts.results import DomainLimitation, MeasureValue
from tesis_domain_extensions.domains.inspection_route.contracts import (
    InspectionConstraintSetResult,
    InspectionDomainRunManifest,
    InspectionExecutionRef,
    InspectionRouteConfig,
    InspectionRouteProjectionContext,
    InspectionRouteResult,
    InspectionScenarioOrigin,
    InspectionScenarioResult,
)
from tesis_domain_extensions.domains.inspection_route.generation import (
    InspectionScenarioGenerator,
)
from tesis_domain_extensions.domains.inspection_route.interpretation import PRIMARY_MEASURE
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_domain_extensions.metrics import exact_fraction, unrestricted_undirected_path_count


def _count_value(result: InspectionScenarioResult) -> int | None:
    count = result.route_count
    if count is None or count.value is None:
        return None
    return int(count.value)


def build_result(
    config: InspectionRouteConfig,
    context: InspectionRouteProjectionContext,
    manifest: InspectionDomainRunManifest,
    constraint_results: list[InspectionConstraintSetResult],
) -> InspectionRouteResult:
    if manifest.status not in {"completed", "failed", "cancelled"}:
        raise DomainExtensionError("La agregación requiere una ejecución terminal.")
    execution_status = cast(Literal["completed", "failed", "cancelled"], manifest.status)
    generator = InspectionScenarioGenerator(config, context)
    generated = list(generator)
    generated_by_scenario = {
        cast(InspectionScenarioOrigin, case.origin).scenario_id: case for case in generated
    }
    invalid_by_scenario = {item.scenario_id: item for item in generator.invalid_scenarios}
    evidence_by_id = {item.constraint_set_id: item for item in constraint_results}
    unrestricted = unrestricted_undirected_path_count(len(config.study.locations))
    scenarios: list[InspectionScenarioResult] = []
    for scenario in config.study.scenarios:
        invalid = invalid_by_scenario.get(scenario.id)
        if invalid is not None:
            scenarios.append(
                InspectionScenarioResult(
                    scenario_id=scenario.id,
                    scenario_title=scenario.title,
                    required_consecutive_visits=scenario.required_consecutive_visits,
                    constraint_set_id=invalid.constraint_set_id,
                    core_run_id=None,
                    feasibility="invalid_constraints",
                    structure=None,
                    route_count=None,
                    retained_route_flexibility=None,
                    validation_issue=invalid.issue,
                    diagnostics=[],
                    technical_metrics=None,
                    limitations=[],
                )
            )
            continue
        projected = generated_by_scenario.get(scenario.id)
        if projected is None:
            raise DomainExtensionError("Falta el caso proyectado para un escenario válido.")
        evidence = evidence_by_id.get(projected.case_id)
        if evidence is None:
            raise DomainExtensionError("Falta evidencia CORE para un escenario válido.")
        count = None if evidence.route_count is None else evidence.route_count.value
        flexibility = None
        if count is not None:
            numeric_count = int(count)
            if numeric_count > unrestricted:
                raise DomainExtensionError(
                    "El CORE informó más recorridos que el universo irrestricto."
                )
            flexibility = MeasureValue(
                measure=PRIMARY_MEASURE,
                value=exact_fraction(numeric_count, unrestricted),
            )
        scenarios.append(
            InspectionScenarioResult(
                scenario_id=scenario.id,
                scenario_title=scenario.title,
                required_consecutive_visits=scenario.required_consecutive_visits,
                constraint_set_id=evidence.constraint_set_id,
                core_run_id=evidence.core_run_id,
                feasibility=evidence.feasibility,
                structure=evidence.structure,
                route_count=evidence.route_count,
                retained_route_flexibility=flexibility,
                validation_issue=None,
                diagnostics=evidence.diagnostics,
                technical_metrics=evidence.technical_metrics,
                limitations=evidence.limitations,
            )
        )
    valid = [item for item in scenarios if item.validation_issue is None]
    counts = [_count_value(item) for item in valid]
    if not valid:
        comparison_status: Literal["conclusive", "inconclusive", "not_applicable"] = (
            "not_applicable"
        )
        most_flexible: list[str] = []
    elif any(value is None for value in counts):
        comparison_status = "inconclusive"
        most_flexible = []
    else:
        comparison_status = "conclusive"
        maximum = max(cast(list[int], counts))
        most_flexible = [
            item.scenario_id for item, value in zip(valid, counts, strict=True) if value == maximum
        ]
    return InspectionRouteResult(
        schema_version="1.0.0",
        domain=config.domain,
        study_id=config.study.id,
        study_title=config.study.title,
        locations=config.study.locations,
        execution=InspectionExecutionRef(
            domain_run_id=manifest.domain_run_id,
            domain_experiment_id=manifest.domain_experiment_id,
            status=execution_status,
        ),
        primary_measure=PRIMARY_MEASURE,
        generation=manifest.generation,
        comparison_status=comparison_status,
        most_flexible_scenario_ids=most_flexible,
        scenarios=scenarios,
        limitations=[
            DomainLimitation(
                code="DOMAIN_SCOPE",
                message=(
                    "El análisis compara obligaciones de consecutividad; no optimiza distancias, "
                    "costos, horarios ni selecciona un recorrido particular."
                ),
            )
        ],
    )
