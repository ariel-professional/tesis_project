from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, ValidationInfo, model_validator

from tesis_domain_extensions.contracts.common import (
    CoreRunAttempt,
    DomainExperimentId,
    DomainRef,
    LargeNonNegativeInteger,
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
    RouteCount,
    TechnicalMetrics,
)
from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
    LayoutCaseOrigin,
    LayoutCasePayload,
    LinearForestStructure,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.contracts import (
    AdjacencyFinding,
    AdjacencyValueMatrix,
    AdjacencyValueResult,
    CapturedFlowResult,
    FlowMatrix,
    ObjectiveReference,
    ObjectiveSnapshot,
    ParetoClassification,
    RelLevelResult,
    RelMatrix,
    RetainedLayoutsResult,
    UndesiredAdjacency,
)


class SingleRowDomainRefV2(DomainRef):
    id: Literal["single-row-facility-layout"]
    version: Literal["2.0.0"]


class StationV2(StrictModel):
    id: Slug
    name: NormalizedText


class LinearComponentV2(StrictModel):
    id: Slug
    station_ids: Annotated[list[Slug], Field(min_length=2)]
    description: NormalizedText | None = None
    attachments: list[Attachment] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_path(self) -> LinearComponentV2:
        if len(set(self.station_ids)) != len(self.station_ids):
            raise ValueError("un componente no puede repetir estaciones")
        return self


class LayoutDesignV2(StrictModel):
    id: Slug
    description: NormalizedText | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    title: NormalizedText
    base_component_ids: list[Slug]

    @model_validator(mode="after")
    def unique_base(self) -> LayoutDesignV2:
        if len(set(self.base_component_ids)) != len(self.base_component_ids):
            raise ValueError("las referencias a componentes base deben ser únicas")
        return self


class LayoutStudyV2(StrictModel):
    id: Slug
    title: NormalizedText
    description: NormalizedText | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    stations: Annotated[list[StationV2], Field(min_length=1)]
    components: Annotated[list[LinearComponentV2], Field(min_length=1)]
    designs: Annotated[list[LayoutDesignV2], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_catalog(self) -> LayoutStudyV2:
        station_ids = [item.id for item in self.stations]
        component_ids = [item.id for item in self.components]
        if len(station_ids) != len(set(station_ids)) or len(component_ids) != len(
            set(component_ids)
        ):
            raise ValueError("los identificadores del estudio deben ser únicos")
        known = set(station_ids)
        paths: set[tuple[str, ...]] = set()
        for component in self.components:
            if not set(component.station_ids) <= known:
                raise ValueError("cada componente debe referenciar estaciones declaradas")
            path = tuple(component.station_ids)
            canonical = min(path, tuple(reversed(path)))
            if canonical in paths:
                raise ValueError("dos componentes iguales o inversos son duplicados")
            paths.add(canonical)
        if len(self.designs) != len({item.id for item in self.designs}):
            raise ValueError("los identificadores de diseños deben ser únicos")
        if sum(not item.base_component_ids for item in self.designs) > 1:
            raise ValueError("sólo puede existir un diseño de control sin restricciones base")
        for design in self.designs:
            if not set(design.base_component_ids) <= set(component_ids):
                raise ValueError("cada diseño debe referenciar componentes declarados")
        return self


def _validate_matrix_identity(matrices: list[AdjacencyValueMatrix]) -> None:
    matrix_ids = [item.id for item in matrices]
    matrix_names = [item.name.casefold() for item in matrices]
    if len(matrix_ids) != len(set(matrix_ids)):
        raise ValueError("los identificadores de matrices deben ser únicos")
    if len(matrix_names) != len(set(matrix_names)):
        raise ValueError("los nombres visibles de matrices deben ser únicos")


class DecisionModelV2(StrictModel):
    selected_objectives: list[ObjectiveReference] = Field(default_factory=list)
    retained_compatible_layouts: bool = False
    rel_closeness: RelMatrix | None = None
    adjacency_flow: FlowMatrix | list[AdjacencyValueMatrix] | None = None
    undesired_prescribed_adjacencies: list[UndesiredAdjacency] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def infer_historical_selected_objectives(cls, value: Any) -> Any:
        if not isinstance(value, dict) or value.get("selected_objectives"):
            return value
        selected: list[dict[str, str]] = []
        if value.get("retained_compatible_layouts", False):
            selected.append({"id": "retained-compatible-layouts", "version": "1"})
        if value.get("rel_closeness") is not None:
            selected.append({"id": "rel-closeness", "version": "1"})
        if value.get("adjacency_flow") is not None:
            selected.append({"id": "captured-adjacency-flow", "version": "1"})
        return {**value, "selected_objectives": selected}

    @model_validator(mode="after")
    def at_least_one_criterion(self) -> DecisionModelV2:
        from .objectives.catalog import resolve_objective

        if not self.selected_objectives:
            raise ValueError("debe seleccionarse al menos un criterio de decisión")
        references = [(item.id, item.version) for item in self.selected_objectives]
        if len(references) != len(set(references)):
            raise ValueError("los criterios de decisión no pueden repetirse")
        available = {"core-layout-count"}
        if self.rel_closeness is not None:
            available.add("rel-matrix")
        if self.adjacency_flow is not None:
            available.add("flow-matrix")
        for reference in self.selected_objectives:
            definition = resolve_objective(reference.id, reference.version)
            if not set(definition.required_inputs) <= available:
                raise ValueError(
                    f"faltan insumos requeridos para {reference.id}@{reference.version}"
                )
        selected_ids = {item.id for item in self.selected_objectives}
        if self.adjacency_flow is not None and "captured-adjacency-flow" not in selected_ids:
            raise ValueError("las matrices cuantitativas requieren seleccionar su criterio")
        pairs = [
            (item.first_station_id, item.second_station_id)
            for item in self.undesired_prescribed_adjacencies
        ]
        if len(pairs) != len(set(pairs)):
            raise ValueError("no se pueden repetir adyacencias inconvenientes")
        if isinstance(self.adjacency_flow, list):
            _validate_matrix_identity(self.adjacency_flow)
        return self


class LayoutReportingV2(StrictModel):
    invalid_combinations: Literal["summary", "full"] = "summary"


class GenerationMetricsV2(StrictModel):
    theoretical_combinations: LargeNonNegativeInteger
    cycle_pruned_branches: LargeNonNegativeInteger
    degree_pruned_branches: LargeNonNegativeInteger
    valid_selections: LargeNonNegativeInteger
    invalid_combinations: LargeNonNegativeInteger
    structural_invalid_combinations: LargeNonNegativeInteger
    forbidden_combinations: LargeNonNegativeInteger
    duplicate_forests: LargeNonNegativeInteger
    core_cases: LargeNonNegativeInteger


class InvalidCombinationSummaryV2(StrictModel):
    reason: Literal["cycle", "degree_exceeded", "forbidden"]
    combination_count: LargeNonNegativeInteger
    affected_station_ids: list[Slug]
    conflicting_edges: list[tuple[Slug, Slug]]
    conflicting_component_ids: list[Slug]
    cause: NormalizedText | None = None
    explanation: NormalizedText | None = None
    provenance: NormalizedText | None = None


def _validate_actionable_objectives(decision: DecisionModelV2, study: LayoutStudyV2) -> None:
    selected_ids = {item.id for item in decision.selected_objectives}
    component_pairs = {
        tuple(sorted((first, second)))
        for component in study.components
        for first, second in zip(component.station_ids, component.station_ids[1:], strict=False)
    }
    if "rel-closeness" in selected_ids and decision.rel_closeness is not None:
        active_levels = {
            item.level
            for item in decision.rel_closeness.requirements
            if item.level in {"A", "E", "I", "O"}
        }
        for level in active_levels:
            level_pairs = {
                (item.first_station_id, item.second_station_id)
                for item in decision.rel_closeness.requirements
                if item.level == level
            }
            if not level_pairs.intersection(component_pairs):
                raise ValueError(f"el nivel REL {level} no tiene ninguna restricción candidata")
    if "captured-adjacency-flow" in selected_ids and decision.adjacency_flow is not None:
        matrices = (
            decision.adjacency_flow
            if isinstance(decision.adjacency_flow, list)
            else [decision.adjacency_flow]
        )
        for matrix in matrices:
            if isinstance(matrix, AdjacencyValueMatrix):
                valued_pairs = {
                    tuple(sorted((item.from_station_id, item.to_station_id)))
                    for item in matrix.entries
                }
            else:
                valued_pairs = {
                    tuple(sorted((item.from_station_id, item.to_station_id)))
                    for item in matrix.entries
                    if item.quantity > 0
                }
            if not valued_pairs.intersection(component_pairs):
                if not isinstance(matrix, AdjacencyValueMatrix):
                    raise ValueError(
                        "el criterio de flujo no tiene restricciones candidatas con movimientos"
                    )
                raise ValueError(f"la matriz {matrix.name} no tiene restricciones candidatas")


def _validate_adjacency_matrices(
    flow: FlowMatrix | list[AdjacencyValueMatrix] | None,
    station_ids: set[str],
    expected_pairs: set[tuple[str, str]],
) -> None:
    if flow is None:
        return
    matrices = flow if isinstance(flow, list) else [flow]
    if not matrices:
        raise ValueError("el criterio de valor de adyacencias requiere al menos una matriz")
    for matrix in matrices:
        actual = {(item.from_station_id, item.to_station_id) for item in matrix.entries}
        expected = (
            {(left, right) for left in station_ids for right in station_ids if left != right}
            if matrix.directed
            else expected_pairs
        )
        if actual != expected:
            raise ValueError("cada matriz de adyacencias debe estar completa y explícita")


class SingleRowFacilityLayoutConfigV2(StrictModel):
    schema_version: Literal["2.0.0"]
    domain: SingleRowDomainRefV2
    study: LayoutStudyV2
    decision_model: DecisionModelV2
    execution: ExecutionConfig
    reporting: LayoutReportingV2 = Field(default_factory=LayoutReportingV2)

    @model_validator(mode="after")
    def validate_problem_size(self, info: ValidationInfo) -> SingleRowFacilityLayoutConfigV2:
        if len(self.study.stations) > self.execution.integer_limits.max_n:
            raise ValueError("la cantidad de estaciones supera integer_limits.max_n")
        station_ids = {item.id for item in self.study.stations}
        ordered_station_ids = sorted(station_ids)
        expected_pairs = {
            (left, right)
            for index, left in enumerate(ordered_station_ids)
            for right in ordered_station_ids[index + 1 :]
        }
        decision = self.decision_model
        if decision.rel_closeness is not None:
            actual = {
                (item.first_station_id, item.second_station_id)
                for item in decision.rel_closeness.requirements
            }
            if actual != expected_pairs:
                raise ValueError("la matriz REL debe contener exactamente todos los pares")
            if not actual <= {pair for pair in expected_pairs}:
                raise ValueError("la matriz REL referencia estaciones desconocidas")
        _validate_adjacency_matrices(decision.adjacency_flow, station_ids, expected_pairs)
        undesired_pairs = {
            (item.first_station_id, item.second_station_id)
            for item in decision.undesired_prescribed_adjacencies
        }
        if not undesired_pairs <= expected_pairs:
            raise ValueError("las adyacencias inconvenientes referencian estaciones desconocidas")
        x_pairs = (
            {
                (item.first_station_id, item.second_station_id)
                for item in decision.rel_closeness.requirements
                if item.level == "X"
            }
            if decision.rel_closeness is not None
            else set()
        )
        if undesired_pairs != x_pairs:
            raise ValueError("cada relación REL X debe tener exactamente una política explícita")
        context = info.context if isinstance(info.context, dict) else {}
        if context.get("historical_projection") is not True:
            _validate_actionable_objectives(decision, self.study)
        return self


class StationVertexV2(StrictModel):
    vertex: int = Field(ge=1)
    station_id: Slug


class SingleRowProjectionContextV2(StrictModel):
    schema_version: Literal["2.0.0"]
    vertex_mapping: list[StationVertexV2]


class SingleRowExperimentProjectionV2(DomainExperimentProjectionBase):
    schema_version: Literal["2.0.0"]  # type: ignore[assignment]
    domain_config: SingleRowFacilityLayoutConfigV2
    projection_context: SingleRowProjectionContextV2
    objective_snapshots: list[ObjectiveSnapshot]

    @model_validator(mode="after")
    def validate_identity(self) -> SingleRowExperimentProjectionV2:
        if self.domain_experiment_id != domain_experiment_id(
            self.domain_config, self.instance_nonce
        ):
            raise ValueError("domain experiment ID does not match its configuration")
        return self


class SingleRowExperimentSummaryV2(DomainExperimentSummaryBase):
    schema_version: Literal["2.0.0"]  # type: ignore[assignment]
    domain: SingleRowDomainRefV2


class SingleRowRunSummaryV2(DomainRunSummaryBase):
    schema_version: Literal["2.0.0"]  # type: ignore[assignment]
    domain: SingleRowDomainRefV2


class LayoutCaseResultV2(StrictModel):
    case_id: DomainExperimentId
    forest_id: DomainExperimentId
    design_id: Slug
    mandatory_component_ids: list[Slug]
    added_component_ids: list[Slug]
    component_ids: list[Slug]
    edges: list[tuple[Slug, Slug]]
    forest_structure: LinearForestStructure
    prescribed_edge_count: int = Field(ge=0)
    core_run_id: RunId
    feasibility: Literal["feasible", "invalid_constraints", "inconclusive"]
    compatible_layout_count: RouteCount | None
    retained_layouts: RetainedLayoutsResult | None = None
    rel_closeness: list[RelLevelResult] = Field(default_factory=list)
    captured_flow: CapturedFlowResult | None = None
    adjacency_values: list[AdjacencyValueResult] = Field(default_factory=list)
    findings: list[AdjacencyFinding] = Field(default_factory=list)
    pareto_classification: ParetoClassification
    technical_metrics: TechnicalMetrics | None
    diagnostics: list[DomainDiagnostic]
    limitations: list[DomainLimitation]


class LayoutDesignResultV2(StrictModel):
    design_id: Slug
    design_title: NormalizedText
    mandatory_component_ids: list[Slug]
    candidate_component_ids: list[Slug]
    theoretical_combinations: LargeNonNegativeInteger
    valid_case_count: LargeNonNegativeInteger
    invalid_combination_count: LargeNonNegativeInteger
    invalid_combination_summaries: list[InvalidCombinationSummaryV2]
    base_case_id: DomainExperimentId
    base_layout_count: RouteCount | None
    cases: list[LayoutCaseResultV2]
    pareto_case_ids: list[DomainExperimentId]


class SingleRowFacilityLayoutResultV2(StrictModel):
    schema_version: Literal["2.0.0"]
    domain: SingleRowDomainRefV2
    study_id: Slug
    study_title: NormalizedText
    study_description: NormalizedText | None
    stations: list[StationV2]
    execution: dict[str, object]
    generation: GenerationMetricsV2
    objective_snapshots: list[ObjectiveSnapshot]
    designs: list[LayoutDesignResultV2]
    limitations: list[DomainLimitation]


class PersistedCaseV2(StrictModel):
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


class RunDesignSummaryV2(StrictModel):
    design_id: Slug
    design_title: NormalizedText
    theoretical_combinations: LargeNonNegativeInteger


class DomainRunManifestV2(StrictModel):
    schema_version: Literal["2.0.0"]
    domain_run_id: RunId
    domain_experiment_id: DomainExperimentId
    domain: SingleRowDomainRefV2
    display_name: NormalizedText
    status: Literal["created", "running", "completed", "failed", "cancelled"]
    generator_cursor: LargeNonNegativeInteger
    generation: GenerationMetricsV2
    designs: list[RunDesignSummaryV2] = Field(default_factory=list)
    cases: list[PersistedCaseV2]
    active_duration_ms: int = Field(default=0, ge=0)
    active_started_at: Timestamp | None = None
    created_at: Timestamp
    updated_at: Timestamp
