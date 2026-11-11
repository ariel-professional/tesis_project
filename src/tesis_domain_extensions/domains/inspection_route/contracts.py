from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from tesis_domain_extensions.contracts.common import (
    CoreRunAttempt,
    DomainExperimentId,
    DomainRef,
    LargeNonNegativeInteger,
    MeasureDefinition,
    NonNegativeInt,
    NormalizedText,
    RunId,
    Slug,
    StrictModel,
    Timestamp,
)
from tesis_domain_extensions.contracts.config import ExecutionConfig
from tesis_domain_extensions.contracts.projection import (
    DomainExperimentProjectionBase,
    DomainExperimentSummaryBase,
    DomainRunSummaryBase,
    domain_experiment_id,
)
from tesis_domain_extensions.contracts.results import (
    DomainDiagnostic,
    DomainLimitation,
    MeasureValue,
    RouteCount,
    TechnicalMetrics,
)


class InspectionRouteDomainRef(DomainRef):
    id: Literal["inspection-route"]
    version: Literal["1.0.0"]


class Location(StrictModel):
    id: Slug
    name: NormalizedText


class InspectionScenario(StrictModel):
    id: Slug
    title: NormalizedText
    required_consecutive_visits: list[tuple[Slug, Slug]]

    @field_validator("required_consecutive_visits", mode="after")
    @classmethod
    def canonicalize_visits(cls, visits: list[tuple[str, str]]) -> list[tuple[str, str]]:
        canonical: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for first, second in visits:
            if first == second:
                raise ValueError("una instalación no puede ser consecutiva consigo misma")
            edge = (first, second) if first < second else (second, first)
            if edge in seen:
                raise ValueError("las visitas consecutivas no dirigidas deben ser únicas")
            seen.add(edge)
            canonical.append(edge)
        return sorted(canonical)


class InspectionStudy(StrictModel):
    id: Slug
    title: NormalizedText
    locations: Annotated[list[Location], Field(min_length=1)]
    scenarios: Annotated[list[InspectionScenario], Field(min_length=2)]

    @model_validator(mode="after")
    def validate_catalog(self) -> InspectionStudy:
        location_ids = [location.id for location in self.locations]
        if len(set(location_ids)) != len(location_ids):
            raise ValueError("los identificadores de instalaciones deben ser únicos")
        known = set(location_ids)
        scenario_ids = [scenario.id for scenario in self.scenarios]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("los identificadores de escenarios deben ser únicos")
        for scenario in self.scenarios:
            if any(
                first not in known or second not in known
                for first, second in scenario.required_consecutive_visits
            ):
                raise ValueError("cada visita consecutiva debe usar instalaciones declaradas")
        return self


class InspectionRouteConfig(StrictModel):
    schema_version: Literal["1.0.0"]
    domain: InspectionRouteDomainRef
    study: InspectionStudy
    execution: ExecutionConfig

    @model_validator(mode="after")
    def validate_problem_size(self) -> InspectionRouteConfig:
        if len(self.study.locations) > self.execution.integer_limits.max_n:
            raise ValueError("la cantidad de instalaciones supera integer_limits.max_n")
        return self


class LocationVertex(StrictModel):
    vertex: Annotated[StrictInt, Field(ge=1)]
    location_id: Slug


class InspectionRouteProjectionContext(StrictModel):
    schema_version: Literal["1.0.0"]
    vertex_mapping: list[LocationVertex]

    @model_validator(mode="after")
    def validate_mapping(self) -> InspectionRouteProjectionContext:
        expected = list(range(1, len(self.vertex_mapping) + 1))
        if [item.vertex for item in self.vertex_mapping] != expected:
            raise ValueError("vertex mapping must contain consecutive vertices starting at one")
        identifiers = [item.location_id for item in self.vertex_mapping]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("vertex mapping location identifiers must be unique")
        return self


class InspectionRouteProjection(DomainExperimentProjectionBase):
    domain_config: InspectionRouteConfig
    projection_context: InspectionRouteProjectionContext

    @model_validator(mode="after")
    def validate_identity(self) -> InspectionRouteProjection:
        if self.domain_experiment_id != domain_experiment_id(
            self.domain_config, self.instance_nonce
        ):
            raise ValueError("domain experiment ID does not match the canonical configuration")
        return self


class InspectionExperimentSummary(DomainExperimentSummaryBase):
    domain: InspectionRouteDomainRef


class InspectionRunSummary(DomainRunSummaryBase):
    domain: InspectionRouteDomainRef


class InspectionScenarioOrigin(StrictModel):
    scenario_id: Slug


class InspectionConstraintPayload(StrictModel):
    required_consecutive_visits: list[tuple[Slug, Slug]]


class InspectionGenerationMetrics(StrictModel):
    declared_scenarios: LargeNonNegativeInteger
    valid_scenarios: LargeNonNegativeInteger
    invalid_scenarios: LargeNonNegativeInteger
    duplicate_constraint_sets: LargeNonNegativeInteger
    core_cases: LargeNonNegativeInteger


class InspectionStructure(StrictModel):
    core_case_type: Literal[
        "empty",
        "hamiltonian_path_extreme",
        "single_edge",
        "matching",
        "single_path",
        "multiple_paths",
    ]
    mandatory_chains: list[list[Slug]]
    unconstrained_locations: list[Slug]
    planning_blocks: NonNegativeInt


class InspectionConstraintIssue(StrictModel):
    reason: Literal["cycle", "degree_exceeded"]
    message: NormalizedText
    affected_location_ids: list[Slug]
    conflicting_consecutive_visits: list[tuple[Slug, Slug]]


class InspectionConstraintSetResult(StrictModel):
    constraint_set_id: DomainExperimentId
    origins: list[InspectionScenarioOrigin]
    required_consecutive_visits: list[tuple[Slug, Slug]]
    core_run_id: RunId
    feasibility: Literal["feasible", "invalid_constraints", "inconclusive"]
    structure: InspectionStructure | None
    route_count: RouteCount | None
    technical_metrics: TechnicalMetrics | None
    diagnostics: list[DomainDiagnostic]
    limitations: list[DomainLimitation]


class InspectionScenarioResult(StrictModel):
    scenario_id: Slug
    scenario_title: NormalizedText
    required_consecutive_visits: list[tuple[Slug, Slug]]
    constraint_set_id: DomainExperimentId
    core_run_id: RunId | None
    feasibility: Literal["feasible", "invalid_constraints", "inconclusive"]
    structure: InspectionStructure | None
    route_count: RouteCount | None
    retained_route_flexibility: MeasureValue | None
    validation_issue: InspectionConstraintIssue | None
    diagnostics: list[DomainDiagnostic]
    technical_metrics: TechnicalMetrics | None
    limitations: list[DomainLimitation]


class InspectionExecutionRef(StrictModel):
    domain_run_id: RunId
    domain_experiment_id: DomainExperimentId
    status: Literal["completed", "failed", "cancelled"]


class InspectionRouteResult(StrictModel):
    schema_version: Literal["1.0.0"]
    domain: InspectionRouteDomainRef
    study_id: Slug
    study_title: NormalizedText
    locations: list[Location]
    execution: InspectionExecutionRef
    primary_measure: MeasureDefinition
    generation: InspectionGenerationMetrics
    comparison_status: Literal["conclusive", "inconclusive", "not_applicable"]
    most_flexible_scenario_ids: list[Slug]
    scenarios: list[InspectionScenarioResult]
    limitations: list[DomainLimitation]


class PersistedConstraintSet(StrictModel):
    constraint_set_id: DomainExperimentId
    core_experiment_id: DomainExperimentId
    origins: list[InspectionScenarioOrigin]
    payload: InspectionConstraintPayload
    attempts: Annotated[list[CoreRunAttempt], Field(min_length=1)]

    @property
    def core_run_id(self) -> str:
        return self.attempts[-1].core_run_id

    @property
    def status(self) -> str:
        return self.attempts[-1].status


class InspectionDomainRunManifest(StrictModel):
    schema_version: Literal["1.0.0"]
    domain_run_id: RunId
    domain_experiment_id: DomainExperimentId
    domain: InspectionRouteDomainRef
    display_name: NormalizedText
    status: Literal["created", "running", "completed", "failed", "cancelled"]
    generator_cursor: LargeNonNegativeInteger
    generation: InspectionGenerationMetrics
    cases: list[PersistedConstraintSet]
    created_at: Timestamp
    updated_at: Timestamp
