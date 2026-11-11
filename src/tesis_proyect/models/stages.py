from typing import Annotated, Literal

from pydantic import Field, StrictInt, model_validator

from tesis_proyect.models.base import StrictModel
from tesis_proyect.models.common import (
    ArtifactRef,
    Hash,
    StructuredError,
    Timestamp,
)
from tesis_proyect.models.enums import STAGE_ORDER, StageId, StageTerminalStatus
from tesis_proyect.models.execution import StageAttempt, StageMetricSummary
from tesis_proyect.models.scientific import (
    ValidationResult,
)


class DefinitionOutcome(StrictModel):
    kind: Literal["definition"]
    config_hash: Hash


class CandidateOutcome(StrictModel):
    kind: Literal["candidate"]
    candidate: ArtifactRef


class EdgeValidationOutcome(StrictModel):
    kind: Literal["edge_validation"]
    validation: ValidationResult
    instance: ArtifactRef | None


class ForestValidationOutcome(StrictModel):
    kind: Literal["forest_validation"]
    validation: ValidationResult


class StructureOutcome(StrictModel):
    kind: Literal["structure_analysis"]
    analysis: ArtifactRef


class ExactOutcome(StrictModel):
    kind: Literal["exact_counting"]
    result: ArtifactRef


class ReferenceOutcome(StrictModel):
    kind: Literal["reference_counting"]
    result: ArtifactRef


class ComparisonOutcome(StrictModel):
    kind: Literal["comparison"]
    result: ArtifactRef


class MetricsOutcome(StrictModel):
    kind: Literal["metrics_collection"]
    stages: Annotated[list[StageMetricSummary], Field(min_length=8, max_length=8)]

    @model_validator(mode="after")
    def validate_stage_order(self) -> "MetricsOutcome":
        if [item.stage for item in self.stages] != list(STAGE_ORDER[:8]):
            raise ValueError("metrics must summarize stages 01 through 08 in order")
        return self


class ReportOutcome(StrictModel):
    kind: Literal["report_export"]
    json_report: ArtifactRef
    markdown_report: ArtifactRef


StageOutcome = Annotated[
    DefinitionOutcome
    | CandidateOutcome
    | EdgeValidationOutcome
    | ForestValidationOutcome
    | StructureOutcome
    | ExactOutcome
    | ReferenceOutcome
    | ComparisonOutcome
    | MetricsOutcome
    | ReportOutcome,
    Field(discriminator="kind"),
]


class StageResult(StrictModel):
    schema_version: Literal["1.0.0"]
    stage: StageId
    status: StageTerminalStatus
    attempts: list[StageAttempt]
    started_at: Timestamp
    finished_at: Timestamp
    duration_ms: Annotated[StrictInt, Field(ge=0)]
    error: StructuredError | None
    artifacts: list[ArtifactRef]
    outcome: StageOutcome | None

    @model_validator(mode="after")
    def validate_attempts(self) -> "StageResult":
        if not self.attempts or [a.number for a in self.attempts] != list(
            range(1, len(self.attempts) + 1)
        ):
            raise ValueError("attempts must be non-empty and consecutive")
        last = self.attempts[-1]
        if (self.status, self.started_at, self.finished_at, self.duration_ms) != (
            last.status,
            last.started_at,
            last.finished_at,
            last.duration_ms,
        ):
            raise ValueError("top-level terminal fields must mirror the last attempt")
        if self.error != last.error:
            raise ValueError("top-level error must mirror the last attempt")
        expected_outcome = {
            StageId.DEFINE_EXPERIMENT: DefinitionOutcome,
            StageId.LOAD_OR_GENERATE_INSTANCE: CandidateOutcome,
            StageId.VALIDATE_INSTANCE_EDGES: EdgeValidationOutcome,
            StageId.VALIDATE_LINEAR_FOREST: ForestValidationOutcome,
            StageId.ANALYZE_STRUCTURE: StructureOutcome,
            StageId.RUN_EXACT_METHOD: ExactOutcome,
            StageId.RUN_REFERENCE_METHOD: ReferenceOutcome,
            StageId.COMPARE_RESULTS: ComparisonOutcome,
            StageId.COLLECT_METRICS: MetricsOutcome,
            StageId.EXPORT_REPORT: ReportOutcome,
        }
        if self.outcome is not None and not isinstance(self.outcome, expected_outcome[self.stage]):
            raise ValueError("outcome does not match stage")
        if self.status == StageTerminalStatus.SUCCESS and self.outcome is None:
            raise ValueError("successful stage requires its outcome")
        if self.status in {StageTerminalStatus.SUCCESS, StageTerminalStatus.SKIPPED}:
            if self.error is not None:
                raise ValueError("success and skipped results have no top-level error")
        elif self.error is None:
            raise ValueError("failed and cancelled results require an error")
        return self
