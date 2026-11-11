from typing import Annotated, Literal

from pydantic import Field, StrictInt, model_validator

from tesis_proyect.models.base import CandidateJsonValue, NfcString, StrictModel
from tesis_proyect.models.common import (
    ArtifactRef,
    AttemptMetrics,
    Cancellation,
    Edge,
    ExperimentId,
    Hash,
    ProducerRef,
    RunId,
    SourceMetadata,
    StructuredError,
    Timestamp,
)
from tesis_proyect.models.enums import (
    STAGE_ORDER,
    CountingConvention,
    ErrorCode,
    RunStatus,
    StageId,
    StageStatus,
    StageTerminalStatus,
)


class InstanceCandidate(StrictModel):
    schema_version: Literal["1.0.0"]
    n: Annotated[StrictInt, Field(ge=1)]
    edge_data: list[CandidateJsonValue]
    source_metadata: SourceMetadata


class Instance(StrictModel):
    schema_version: Literal["1.0.0"]
    n: Annotated[StrictInt, Field(ge=1)]
    vertex_base: Literal[1]
    edges: list[Edge]
    source_metadata: SourceMetadata
    instance_hash: Hash

    @model_validator(mode="after")
    def validate_canonical_edges(self) -> "Instance":
        previous: Edge | None = None
        for edge in self.edges:
            u, v = edge
            if u >= v or v > self.n:
                raise ValueError("instance edges must be normalized and in range")
            if previous is not None and edge <= previous:
                raise ValueError("instance edges must be sorted and unique")
            previous = edge
        return self


class Versions(StrictModel):
    app: ProducerRef
    schema_ref: ProducerRef = Field(alias="schema", serialization_alias="schema")
    pipeline: ProducerRef
    problem: ProducerRef
    generator: ProducerRef | None
    exact: ProducerRef | None
    reference: ProducerRef | None

    @model_validator(mode="after")
    def validate_producer_contract(self) -> "Versions":
        if self.app != ProducerRef(id="tesis-proyect", version="0.1.0"):
            raise ValueError("app producer does not match the public contract")
        if self.schema_ref != ProducerRef(id="public-json", version="1.0.0"):
            raise ValueError("schema producer does not match the public contract")
        if self.pipeline != ProducerRef(id="increment-1", version="1.0.0"):
            raise ValueError("pipeline producer does not match the public contract")
        if self.problem != ProducerRef(id="undirected-path-extension", version="1.0.0"):
            raise ValueError("problem producer does not match the public contract")
        if self.generator is not None and self.generator != ProducerRef(
            id="builtin", version="builtin-v1"
        ):
            raise ValueError("generator producer does not match the public contract")
        if self.exact is not None and self.exact != ProducerRef(
            id="linear-forest-closed-form", version="1"
        ):
            raise ValueError("exact producer does not match the approved closed-form engine")
        if self.reference != ProducerRef(id="bruteforce-python", version="1"):
            raise ValueError("reference producer does not match the public contract")
        return self


class RunManifest(StrictModel):
    schema_version: Literal["1.0.0"]
    run_id: RunId
    experiment_id: ExperimentId
    run_config_hash: Hash
    instance_hash: Hash | None
    counting_convention: CountingConvention
    versions: Versions
    status: RunStatus
    created_at: Timestamp
    updated_at: Timestamp
    cancellation: Cancellation | None


class StageState(StrictModel):
    ordinal: Annotated[StrictInt, Field(ge=1, le=10)]
    stage: StageId
    status: StageStatus
    attempt_count: Annotated[StrictInt, Field(ge=0)]
    result: ArtifactRef | None

    @model_validator(mode="after")
    def validate_result_reference(self) -> "StageState":
        terminal = self.status not in {StageStatus.PENDING, StageStatus.RUNNING}
        if terminal != (self.result is not None):
            raise ValueError("only terminal stage states have result references")
        return self


class PipelineState(StrictModel):
    schema_version: Literal["1.0.0"]
    pipeline_version: Literal["1.0.0"]
    ordered_stages: list[StageState]

    @model_validator(mode="after")
    def validate_order(self) -> "PipelineState":
        expected = [(index, stage) for index, stage in enumerate(STAGE_ORDER, start=1)]
        actual = [(item.ordinal, item.stage) for item in self.ordered_stages]
        if actual != expected:
            raise ValueError("pipeline must contain all ten stages in canonical order")
        if sum(item.status == StageStatus.RUNNING for item in self.ordered_stages) > 1:
            raise ValueError("at most one stage may be running")
        return self


class SkipCause(StrictModel):
    kind: Literal["own", "dependency"]
    code: ErrorCode
    message: Annotated[NfcString, Field(min_length=1, max_length=512)]

    @model_validator(mode="after")
    def validate_kind(self) -> "SkipCause":
        own = {
            ErrorCode.EXACT_ENGINE_NOT_AVAILABLE,
            ErrorCode.BRUTE_FORCE_LIMIT_EXCEEDED,
        }
        if self.kind == "own" and self.code not in own:
            raise ValueError("own skip must be one of the two permitted omissions")
        if self.kind == "dependency" and self.code in own:
            raise ValueError("dependency skip cannot claim an own omission")
        return self


class StageAttempt(StrictModel):
    number: Annotated[StrictInt, Field(ge=1)]
    started_at: Timestamp
    finished_at: Timestamp
    duration_ms: Annotated[StrictInt, Field(ge=0)]
    status: StageTerminalStatus
    error: StructuredError | None
    skip: SkipCause | None
    metrics: AttemptMetrics
    termination: Literal["not_applicable", "cooperative", "forced"]

    @model_validator(mode="after")
    def validate_variant(self) -> "StageAttempt":
        if self.status == StageTerminalStatus.SUCCESS and (
            self.error is not None or self.skip is not None
        ):
            raise ValueError("success has no error or skip")
        if self.status == StageTerminalStatus.FAILED and (
            self.error is None or self.skip is not None
        ):
            raise ValueError("failure requires only an error")
        if self.status == StageTerminalStatus.SKIPPED and (
            self.skip is None or self.error is not None
        ):
            raise ValueError("skip requires only a cause")
        if self.status == StageTerminalStatus.CANCELLED and (
            self.error is None
            or self.error.code != ErrorCode.RUN_CANCELLED
            or self.skip is not None
        ):
            raise ValueError("cancelled attempt requires only RUN_CANCELLED")
        return self


MeasuredStageId = Literal[
    "define_experiment",
    "load_or_generate_instance",
    "validate_instance_edges",
    "validate_linear_forest",
    "analyze_structure",
    "run_exact_method",
    "run_reference_method",
    "compare_results",
]


class StageMetricSummary(StrictModel):
    stage: MeasuredStageId
    attempt_number: Annotated[StrictInt, Field(ge=1)]
    status: StageTerminalStatus
    termination: Literal["not_applicable", "cooperative", "forced"]
    metrics: AttemptMetrics


InstanceCandidate.model_rebuild()
