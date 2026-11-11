from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, StrictInt, model_validator

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
from tesis_domain_extensions.contracts.evidence import Attachment
from tesis_domain_extensions.contracts.projection import (
    DomainExperimentProjectionBase,
    DomainExperimentSummaryBase,
    DomainRunSummaryBase,
    domain_experiment_id,
)
from tesis_domain_extensions.contracts.results import (
    DomainDiagnostic,
    DomainLimitation,
    ExactFraction,
    RouteCount,
    TechnicalMetrics,
)


class SingleRowDomainRef(DomainRef):
    id: Literal["single-row-facility-layout"]
    version: Literal["1.0.0"]


class Station(StrictModel):
    id: Slug
    name: NormalizedText


class LinearComponent(StrictModel):
    id: Slug
    station_ids: Annotated[list[Slug], Field(min_length=2)]
    utility: NonNegativeInt
    description: NormalizedText | None = None
    attachments: list[Attachment] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_path(self) -> LinearComponent:
        if len(set(self.station_ids)) != len(self.station_ids):
            raise ValueError("un componente no puede repetir estaciones")
        return self


class LayoutDesign(StrictModel):
    id: Slug
    description: NormalizedText | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    title: NormalizedText
    base_component_ids: Annotated[list[Slug], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_base_references(self) -> LayoutDesign:
        if len(set(self.base_component_ids)) != len(self.base_component_ids):
            raise ValueError("las referencias a componentes base deben ser únicas")
        return self


class LayoutStudy(StrictModel):
    id: Slug
    title: NormalizedText
    description: NormalizedText | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    stations: Annotated[list[Station], Field(min_length=1)]
    components: Annotated[list[LinearComponent], Field(min_length=1)]
    designs: Annotated[list[LayoutDesign], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_catalog(self) -> LayoutStudy:
        station_ids = [station.id for station in self.stations]
        if len(set(station_ids)) != len(station_ids):
            raise ValueError("los identificadores de estaciones deben ser únicos")
        known_stations = set(station_ids)
        component_ids = [component.id for component in self.components]
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("los identificadores de componentes deben ser únicos")
        canonical_paths: set[tuple[str, ...]] = set()
        for component in self.components:
            if not set(component.station_ids) <= known_stations:
                raise ValueError("cada componente debe referenciar estaciones declaradas")
            path = tuple(component.station_ids)
            canonical = min(path, tuple(reversed(path)))
            if canonical in canonical_paths:
                raise ValueError("dos componentes iguales o inversos son duplicados")
            canonical_paths.add(canonical)
        design_ids = [design.id for design in self.designs]
        if len(set(design_ids)) != len(design_ids):
            raise ValueError("los identificadores de diseños deben ser únicos")
        known_components = set(component_ids)
        for design in self.designs:
            if not set(design.base_component_ids) <= known_components:
                raise ValueError("cada diseño debe referenciar componentes declarados")
        return self


class LayoutReporting(StrictModel):
    invalid_combinations: Literal["summary", "full"]


class SingleRowFacilityLayoutConfig(StrictModel):
    schema_version: Literal["1.0.0"]
    domain: SingleRowDomainRef
    study: LayoutStudy
    execution: ExecutionConfig
    reporting: LayoutReporting

    @model_validator(mode="after")
    def validate_problem_size(self) -> SingleRowFacilityLayoutConfig:
        if len(self.study.stations) > self.execution.integer_limits.max_n:
            raise ValueError("la cantidad de estaciones supera integer_limits.max_n")
        return self


class StationVertex(StrictModel):
    vertex: Annotated[StrictInt, Field(ge=1)]
    station_id: Slug


class SingleRowProjectionContext(StrictModel):
    schema_version: Literal["1.0.0"]
    vertex_mapping: list[StationVertex]

    @model_validator(mode="after")
    def validate_mapping(self) -> SingleRowProjectionContext:
        if [item.vertex for item in self.vertex_mapping] != list(
            range(1, len(self.vertex_mapping) + 1)
        ):
            raise ValueError("vertex mapping must be consecutive and start at one")
        identifiers = [item.station_id for item in self.vertex_mapping]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("station identifiers in the mapping must be unique")
        return self


class SingleRowExperimentProjection(DomainExperimentProjectionBase):
    domain_config: SingleRowFacilityLayoutConfig
    projection_context: SingleRowProjectionContext

    @model_validator(mode="after")
    def validate_identity(self) -> SingleRowExperimentProjection:
        current_id = domain_experiment_id(self.domain_config)
        accepted_ids = {domain_experiment_id(self.domain_config, self.instance_nonce)}
        if self.instance_nonce is None:
            accepted_ids.add(current_id)
        legacy_config = self.domain_config.model_dump(mode="json")
        study = legacy_config["study"]
        entities = [*study["components"], *study["designs"]]
        # Only the two published historical shapes are admitted, and only when
        # all newly introduced documentary fields are empty.
        if not study["attachments"] and all(
            not item["attachments"] and item["description"] is None for item in entities
        ):
            study.pop("attachments")
            for item in entities:
                item.pop("attachments")
                item.pop("description")
            for omit_description in (False, True):
                if omit_description and study.get("description") is None:
                    study.pop("description", None)
                accepted_ids.add(
                    hashlib.sha256(
                        json.dumps(
                            legacy_config, ensure_ascii=False, separators=(",", ":"), sort_keys=True
                        ).encode("utf-8")
                    ).hexdigest()
                )
        if self.domain_experiment_id not in accepted_ids:
            raise ValueError("domain experiment ID does not match its configuration")
        return self


class SingleRowExperimentSummary(DomainExperimentSummaryBase):
    domain: SingleRowDomainRef


class SingleRowRunSummary(DomainRunSummaryBase):
    domain: SingleRowDomainRef


class LayoutCaseOrigin(StrictModel):
    design_id: Slug
    added_component_ids: list[Slug]


class LayoutCasePayload(StrictModel):
    component_ids: list[Slug]
    edges: list[tuple[Slug, Slug]]


class GenerationMetrics(StrictModel):
    theoretical_combinations: LargeNonNegativeInteger
    cycle_pruned_branches: LargeNonNegativeInteger
    degree_pruned_branches: LargeNonNegativeInteger
    valid_selections: LargeNonNegativeInteger
    invalid_combinations: LargeNonNegativeInteger
    duplicate_forests: LargeNonNegativeInteger
    core_cases: LargeNonNegativeInteger


class LayoutForestResult(StrictModel):
    forest_id: DomainExperimentId
    origins: list[LayoutCaseOrigin]
    edges: list[tuple[Slug, Slug]]
    core_run_id: RunId
    feasibility: Literal["feasible", "invalid_constraints", "inconclusive"]
    compatible_layout_count: RouteCount | None
    technical_metrics: TechnicalMetrics | None
    diagnostics: list[DomainDiagnostic]
    limitations: list[DomainLimitation]


class LinearForestStructure(StrictModel):
    paths: list[list[Slug]]
    isolated_station_ids: list[Slug]


class LayoutCaseResult(StrictModel):
    case_id: DomainExperimentId
    forest_id: DomainExperimentId
    design_id: Slug
    mandatory_component_ids: list[Slug]
    added_component_ids: list[Slug]
    component_ids: list[Slug]
    edges: list[tuple[Slug, Slug]]
    forest_structure: LinearForestStructure
    prescribed_edge_count: NonNegativeInt
    utility: LargeNonNegativeInteger
    total_utility: LargeNonNegativeInteger
    core_run_id: RunId
    feasibility: Literal["feasible", "invalid_constraints", "inconclusive"]
    compatible_layout_count: RouteCount | None
    availability_ratio: ExactFraction | None
    restrictiveness_ratio: ExactFraction | None
    technical_metrics: TechnicalMetrics | None
    diagnostics: list[DomainDiagnostic]
    limitations: list[DomainLimitation]
    dominated: bool | None
    pareto_optimal: bool | None

    @model_validator(mode="after")
    def validate_classification(self) -> LayoutCaseResult:
        if (self.dominated, self.pareto_optimal) not in {
            (True, False),
            (False, True),
            (None, None),
        }:
            raise ValueError("dominance and Pareto flags must be complementary or inconclusive")
        return self


class InvalidCombination(StrictModel):
    case_id: DomainExperimentId
    design_id: Slug
    added_component_ids: list[Slug]
    reason: Literal["cycle", "degree_exceeded"]
    affected_station_ids: list[Slug]
    conflicting_edges: list[tuple[Slug, Slug]]
    conflicting_component_ids: list[Slug]


class InvalidConflictSummary(StrictModel):
    reason: Literal["cycle", "degree_exceeded"]
    affected_station_ids: list[Slug]
    conflicting_edges: list[tuple[Slug, Slug]]
    conflicting_component_ids: list[Slug]
    combination_count: LargeNonNegativeInteger


class LayoutDesignResult(StrictModel):
    design_id: Slug
    design_title: NormalizedText
    mandatory_component_ids: list[Slug]
    candidate_component_ids: list[Slug]
    theoretical_combinations: LargeNonNegativeInteger
    valid_case_count: LargeNonNegativeInteger
    invalid_combination_count: LargeNonNegativeInteger
    base_case_id: DomainExperimentId
    base_layout_count: RouteCount | None
    cases: list[LayoutCaseResult]
    invalid_conflicts: list[InvalidConflictSummary]
    invalid_combinations: list[InvalidCombination] | None
    pareto_case_ids: list[DomainExperimentId]


class DomainExecutionRef(StrictModel):
    domain_run_id: RunId
    domain_experiment_id: DomainExperimentId
    status: Literal["completed", "failed", "cancelled"]


class SingleRowFacilityLayoutResult(StrictModel):
    schema_version: Literal["1.0.0"]
    domain: SingleRowDomainRef
    study_id: Slug
    study_title: NormalizedText
    study_description: NormalizedText | None
    stations: list[Station]
    execution: DomainExecutionRef
    primary_measure: MeasureDefinition
    generation: GenerationMetrics
    designs: list[LayoutDesignResult]
    limitations: list[DomainLimitation]


class PersistedCase(StrictModel):
    forest_id: DomainExperimentId
    core_experiment_id: DomainExperimentId
    origins: list[LayoutCaseOrigin]
    payload: LayoutCasePayload
    attempts: Annotated[list[CoreRunAttempt], Field(min_length=1)]

    @property
    def core_run_id(self) -> str:
        return self.attempts[-1].core_run_id

    @property
    def status(self) -> str:
        return self.attempts[-1].status


class DomainRunManifest(StrictModel):
    schema_version: Literal["1.0.0"]
    domain_run_id: RunId
    domain_experiment_id: DomainExperimentId
    domain: SingleRowDomainRef
    display_name: NormalizedText
    status: Literal["created", "running", "completed", "failed", "cancelled"]
    generator_cursor: LargeNonNegativeInteger
    generation: GenerationMetrics
    cases: list[PersistedCase]
    created_at: Timestamp
    updated_at: Timestamp
