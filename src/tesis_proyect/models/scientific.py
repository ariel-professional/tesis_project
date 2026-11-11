from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from tesis_proyect.models.base import LargeNonNegativeInteger, StrictModel
from tesis_proyect.models.common import (
    AttemptMetrics,
    Diagnostic,
    Edge,
    Hash,
    ProducerRef,
    Vertex,
)
from tesis_proyect.models.enums import ComparisonStatus, CountingConvention
from tesis_proyect.models.execution import SkipCause


class ValidationResult(StrictModel):
    schema_version: Literal["1.0.0"]
    valid: StrictBool
    errors: list[Diagnostic]
    warnings: list[Diagnostic]

    @model_validator(mode="after")
    def validate_consistency(self) -> "ValidationResult":
        if self.valid == bool(self.errors):
            raise ValueError("valid must be equivalent to an empty error list")
        return self


class PathComponent(StrictModel):
    vertices: list[Vertex]
    edges: list[Edge]
    edge_length: Annotated[StrictInt, Field(ge=1)]


class LinearForestAnalysis(StrictModel):
    schema_version: Literal["1.0.0"]
    components: list[PathComponent]
    component_lengths: list[Annotated[StrictInt, Field(ge=1)]]
    free_vertices: list[Vertex]
    free_vertex_count: Annotated[StrictInt, Field(ge=0)]
    blocks: Annotated[StrictInt, Field(ge=1)]
    case_type: Literal[
        "empty",
        "hamiltonian_path_extreme",
        "single_edge",
        "matching",
        "single_path",
        "multiple_paths",
    ]

    @model_validator(mode="after")
    def validate_summary(self) -> "LinearForestAnalysis":
        if self.component_lengths != [item.edge_length for item in self.components]:
            raise ValueError("component_lengths must mirror components")
        if self.free_vertex_count != len(self.free_vertices):
            raise ValueError("free_vertex_count mismatch")
        if self.blocks != len(self.components) + self.free_vertex_count:
            raise ValueError("blocks mismatch")
        return self


class CountingSuccess(StrictModel):
    schema_version: Literal["1.0.0"]
    status: Literal["success"]
    value: LargeNonNegativeInteger
    engine: ProducerRef
    formulation: StrictStr
    counting_convention: CountingConvention
    metrics: AttemptMetrics
    instance_hash: Hash
    skip: None

    @model_validator(mode="after")
    def validate_producer(self) -> "CountingSuccess":
        if self.metrics.producer != self.engine:
            raise ValueError("counting metrics producer must match engine")
        return self


class CountingSkipped(StrictModel):
    schema_version: Literal["1.0.0"]
    status: Literal["skipped"]
    value: None
    engine: ProducerRef
    formulation: StrictStr | None
    counting_convention: CountingConvention
    metrics: AttemptMetrics
    instance_hash: Hash
    skip: SkipCause

    @model_validator(mode="after")
    def validate_skip(self) -> "CountingSkipped":
        if self.skip.kind != "own":
            raise ValueError("counting results may only contain an own skip")
        if self.metrics.producer != self.engine:
            raise ValueError("counting metrics producer must match engine")
        return self


CountingResult = Annotated[CountingSuccess | CountingSkipped, Field(discriminator="status")]


class ComparisonResult(StrictModel):
    schema_version: Literal["1.0.0"]
    status: ComparisonStatus
    value_exact: LargeNonNegativeInteger | None
    value_reference: LargeNonNegativeInteger | None
    exact: ProducerRef | None
    reference: ProducerRef | None
    counting_convention: CountingConvention
    reason: SkipCause | None
    instance_hash: Hash

    @model_validator(mode="after")
    def validate_variant(self) -> "ComparisonResult":
        applicable = self.status in {ComparisonStatus.MATCH, ComparisonStatus.MISMATCH}
        values_present = all(
            value is not None
            for value in (self.value_exact, self.value_reference, self.exact, self.reference)
        )
        if applicable and (not values_present or self.reason is not None):
            raise ValueError("applicable comparison requires both results and no reason")
        if not applicable and self.reason is None:
            raise ValueError("not_applicable comparison requires a reason")
        if not applicable and self.reason is not None and self.reason.kind != "own":
            raise ValueError("not_applicable comparison requires an own skip")
        if self.status == ComparisonStatus.MATCH and self.value_exact != self.value_reference:
            raise ValueError("match requires equal values")
        if self.status == ComparisonStatus.MISMATCH and self.value_exact == self.value_reference:
            raise ValueError("mismatch requires distinct values")
        return self
