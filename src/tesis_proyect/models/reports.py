from typing import Literal

from pydantic import model_validator

from tesis_proyect.models.base import StrictModel
from tesis_proyect.models.common import Diagnostic, ExperimentId, RunId
from tesis_proyect.models.enums import STAGE_ORDER, RunStatus
from tesis_proyect.models.execution import Instance, StageMetricSummary
from tesis_proyect.models.scientific import (
    ComparisonResult,
    CountingResult,
    LinearForestAnalysis,
)


class ReportMethods(StrictModel):
    exact: CountingResult | None
    reference: CountingResult | None


class ReportSummary(StrictModel):
    schema_version: Literal["1.0.0"]
    run_id: RunId
    experiment_id: ExperimentId
    run_status: RunStatus
    instance: Instance | None
    structure: LinearForestAnalysis | None
    methods: ReportMethods
    comparison: ComparisonResult | None
    metrics: list[StageMetricSummary] | None
    diagnostics: list[Diagnostic]

    @model_validator(mode="after")
    def validate_metrics(self) -> "ReportSummary":
        if self.metrics is not None and [item.stage for item in self.metrics] != list(
            STAGE_ORDER[:8]
        ):
            raise ValueError("report metrics must summarize stages 01 through 08")
        return self
