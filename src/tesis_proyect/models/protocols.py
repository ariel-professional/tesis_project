from typing import Annotated, Literal

from pydantic import Field, StrictInt, model_validator

from tesis_proyect.models.base import NfcString, StrictModel
from tesis_proyect.models.common import (
    ArtifactRef,
    AttemptMetrics,
    Cancellation,
    ProducerRef,
    RunId,
    StructuredError,
    Timestamp,
)
from tesis_proyect.models.enums import CountingConvention, StageId, StageTerminalStatus
from tesis_proyect.models.execution import (
    Instance,
    PipelineState,
    RunManifest,
)
from tesis_proyect.models.scientific import CountingResult
from tesis_proyect.models.stages import (
    StageResult,
)


class RunCreatedPayload(StrictModel):
    status: Literal["created"]


class RunningPayload(StrictModel):
    status: Literal["running"]


class RunResumedPayload(StrictModel):
    status: Literal["running"]
    from_stage: StageId


class InterruptionPayload(StrictModel):
    status: Literal["running"]
    stage: StageId | None


class StageStartedPayload(StrictModel):
    status: Literal["running"]
    attempt: Annotated[StrictInt, Field(ge=1)]


class StageTerminalPayload(StrictModel):
    status: StageTerminalStatus
    attempt: Annotated[StrictInt, Field(ge=1)]
    result: ArtifactRef


class CancellationAcceptedPayload(StrictModel):
    status: Literal["accepted"]
    requested_at: Timestamp


class ReportExportedPayload(StrictModel):
    status: Literal["success"]
    json_report: ArtifactRef
    markdown_report: ArtifactRef


class RunTerminalPayload(StrictModel):
    status: Literal["completed", "failed", "cancelled"]


class DiagnosticPayload(StrictModel):
    error: StructuredError


EventPayload = (
    RunCreatedPayload
    | RunningPayload
    | RunResumedPayload
    | InterruptionPayload
    | StageStartedPayload
    | StageTerminalPayload
    | CancellationAcceptedPayload
    | ReportExportedPayload
    | RunTerminalPayload
    | DiagnosticPayload
)
EventName = Literal[
    "run_created",
    "run_started",
    "run_resumed",
    "run_interruption_detected",
    "stage_started",
    "stage_terminal",
    "cancellation_accepted",
    "report_exported",
    "run_terminal",
    "diagnostic",
]


class EventEnvelope(StrictModel):
    schema_version: Literal["1.0.0"]
    event: EventName
    run_id: RunId | None
    timestamp: Timestamp
    stage: StageId | None
    payload: EventPayload

    @model_validator(mode="after")
    def validate_payload(self) -> "EventEnvelope":
        expected: dict[str, type[StrictModel]] = {
            "run_created": RunCreatedPayload,
            "run_started": RunningPayload,
            "run_resumed": RunResumedPayload,
            "run_interruption_detected": InterruptionPayload,
            "stage_started": StageStartedPayload,
            "stage_terminal": StageTerminalPayload,
            "cancellation_accepted": CancellationAcceptedPayload,
            "report_exported": ReportExportedPayload,
            "run_terminal": RunTerminalPayload,
            "diagnostic": DiagnosticPayload,
        }
        if not isinstance(self.payload, expected[self.event]):
            raise ValueError("payload does not match event")
        if self.run_id is None and self.event != "diagnostic":
            raise ValueError("only diagnostic may omit run_id")
        stage_events = {"stage_started", "stage_terminal"}
        if (self.stage is not None) != (self.event in stage_events):
            raise ValueError("stage is present only for stage events")
        return self


class RunInspection(StrictModel):
    schema_version: Literal["1.0.0"]
    view: Literal["run"]
    run: RunManifest
    pipeline: PipelineState


class StageInspection(StrictModel):
    schema_version: Literal["1.0.0"]
    view: Literal["stage"]
    run_id: RunId
    stage: StageId
    result: StageResult


class WorkerLimits(StrictModel):
    timeout_ms: Annotated[StrictInt, Field(ge=1)]
    max_message_bytes: Annotated[StrictInt, Field(ge=1)]
    reference_max_n: Annotated[StrictInt, Field(ge=1)]


class WorkerRequest(StrictModel):
    schema_version: Literal["1.0.0"]
    request_id: RunId
    run_id: RunId
    stage: Literal["run_exact_method", "run_reference_method"]
    instance: Instance
    producer: ProducerRef
    limits: WorkerLimits
    counting_convention: CountingConvention


class WorkerResponse(StrictModel):
    schema_version: Literal["1.0.0"]
    request_id: RunId
    run_id: RunId
    stage: Literal["run_exact_method", "run_reference_method"]
    status: Literal["success", "skipped", "failed"]
    result: CountingResult | None
    error: StructuredError | None
    metrics: AttemptMetrics

    @model_validator(mode="after")
    def validate_variant(self) -> "WorkerResponse":
        if self.status == "failed":
            if self.result is not None or self.error is None:
                raise ValueError("failed response requires only an error")
        elif self.result is None or self.error is not None or self.result.status != self.status:
            raise ValueError("successful/skipped response requires matching result only")
        return self


class ControlRequest(StrictModel):
    schema_version: Literal["1.0.0"]
    request_id: RunId
    command: Literal["cancel"]
    run_id: RunId
    requested_at: Timestamp
    origin: Literal["cli"]
    reason: Annotated[NfcString, Field(max_length=512)] | None


class ControlResponse(StrictModel):
    schema_version: Literal["1.0.0"]
    request_id: RunId
    run_id: RunId
    status: Literal["accepted", "already_registered", "terminal", "rejected"]
    cancellation: Cancellation | None
    error: StructuredError | None

    @model_validator(mode="after")
    def validate_variant(self) -> "ControlResponse":
        if self.status in {"accepted", "already_registered"} and self.cancellation is None:
            raise ValueError("accepted cancellation response requires cancellation data")
        if self.status == "rejected" and self.error is None:
            raise ValueError("rejected response requires error")
        if self.status != "rejected" and self.error is not None:
            raise ValueError("only rejected response has error")
        return self
