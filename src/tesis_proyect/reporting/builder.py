"""Build report models from persisted run evidence."""

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import Diagnostic
from tesis_proyect.models.enums import STAGE_ORDER, RunStatus
from tesis_proyect.models.execution import Instance
from tesis_proyect.models.reports import ReportMethods, ReportSummary
from tesis_proyect.models.scientific import (
    ComparisonResult,
    CountingResult,
    LinearForestAnalysis,
)
from tesis_proyect.models.stages import (
    EdgeValidationOutcome,
    ForestValidationOutcome,
    MetricsOutcome,
)
from tesis_proyect.persistence.run_repository import RunRepository


class ReportBuilder:
    """Derive one report view from confirmed run evidence without mutation."""

    def __init__(self, repository: RunRepository) -> None:
        self.repository = repository

    def build(self, status: RunStatus | None = None) -> ReportSummary:
        manifest = self.repository.load_manifest()
        diagnostics: list[Diagnostic] = []
        metrics = None
        for stage in STAGE_ORDER:
            result = self.repository.optional_stage(stage)
            if result is None:
                continue
            if isinstance(result.outcome, MetricsOutcome):
                metrics = result.outcome.stages
            if isinstance(result.outcome, (EdgeValidationOutcome, ForestValidationOutcome)):
                diagnostics.extend(result.outcome.validation.errors)
        return ReportSummary(
            schema_version="1.0.0",
            run_id=manifest.run_id,
            experiment_id=manifest.experiment_id,
            run_status=status or manifest.status,
            instance=self.repository.optional_artifact("instance.json", Instance),
            structure=self.repository.optional_artifact(
                "structure_summary.json", LinearForestAnalysis
            ),
            methods=ReportMethods(
                exact=self._optional_counting("exact_result.json"),
                reference=self._optional_counting("reference_result.json"),
            ),
            comparison=self.repository.optional_artifact(
                "comparison_result.json", ComparisonResult
            ),
            metrics=metrics,
            diagnostics=diagnostics,
        )

    def _optional_counting(self, name: str) -> CountingResult | None:
        try:
            return self.repository.optional_counting(name)
        except (OperationalError, ValueError):
            return None
