from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import TypeAdapter

from tesis_proyect.domain.analysis import validate_analysis_integrity
from tesis_proyect.domain.hashing import instance_hash, run_config_hash
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import STAGE_ORDER, ErrorCode, StageId, StageStatus
from tesis_proyect.models.execution import Instance, PipelineState, RunManifest
from tesis_proyect.models.reports import ReportSummary
from tesis_proyect.models.scientific import (
    ComparisonResult,
    CountingResult,
    CountingSkipped,
    CountingSuccess,
    LinearForestAnalysis,
)
from tesis_proyect.models.stages import (
    CandidateOutcome,
    ComparisonOutcome,
    DefinitionOutcome,
    EdgeValidationOutcome,
    ExactOutcome,
    ForestValidationOutcome,
    MetricsOutcome,
    ReferenceOutcome,
    ReportOutcome,
    StageResult,
    StructureOutcome,
)
from tesis_proyect.persistence.run_repository import RunRepository
from tesis_proyect.reporting.builder import ReportBuilder
from tesis_proyect.reporting.render import render_json, render_markdown


@dataclass(frozen=True)
class ReconciliationResult:
    histories: dict[StageId, StageResult]
    reusable: set[StageId]
    boundary: StageId | None
    discarded_histories: tuple[StageId, ...]


class CheckpointReconciler:
    """Reconcile the fixed ten-stage pipeline without hiding its domain rules."""

    def __init__(
        self,
        repository: RunRepository,
        config: ExperimentConfig,
        manifest: RunManifest,
        pipeline: PipelineState,
    ) -> None:
        self.repository = repository
        self.store = repository.store
        self.config = config
        self.manifest = manifest
        self.pipeline = pipeline
        self.discarded_histories: list[StageId] = []

    def histories(self) -> dict[StageId, StageResult]:
        found: dict[StageId, StageResult] = {}
        for stage in STAGE_ORDER:
            if not self.repository.exists(self.repository.layout.stage(stage)):
                continue
            try:
                found[stage] = self.repository.load_stage(stage)
            except OperationalError:
                self.discarded_histories.append(stage)
                continue
        return found

    def reconcile(self) -> ReconciliationResult:
        self.validate_compatibility()

        histories = self.histories()
        integral = {
            stage: self._is_integral(stage, result, histories)
            for stage, result in histories.items()
        }

        stage_three = histories.get(StageId.VALIDATE_INSTANCE_EDGES)
        if (
            StageId.LOAD_OR_GENERATE_INSTANCE in histories
            and not integral.get(StageId.LOAD_OR_GENERATE_INSTANCE, False)
            and stage_three is not None
            and integral.get(StageId.VALIDATE_INSTANCE_EDGES, False)
            and stage_three.status == "success"
        ):
            integral[StageId.LOAD_OR_GENERATE_INSTANCE] = True

        reusable: set[StageId] = set()
        boundary: StageId | None = None
        for stage in STAGE_ORDER:
            result = histories.get(stage)
            if boundary is None and result is not None and integral.get(stage, False):
                reusable.add(stage)
                reference = self.store.artifact_ref(self.repository.layout.stage(stage))
                state = self.pipeline.ordered_stages[STAGE_ORDER.index(stage)]
                self.pipeline.ordered_stages[STAGE_ORDER.index(stage)] = state.model_copy(
                    update={
                        "status": StageStatus(result.status.value),
                        "attempt_count": len(result.attempts),
                        "result": reference,
                    }
                )
                continue
            if boundary is None:
                boundary = stage
            attempts = len(result.attempts) if result is not None else 0
            state = self.pipeline.ordered_stages[STAGE_ORDER.index(stage)]
            self.pipeline.ordered_stages[STAGE_ORDER.index(stage)] = state.model_copy(
                update={"status": StageStatus.PENDING, "attempt_count": attempts, "result": None}
            )

        instance_result = histories.get(StageId.VALIDATE_INSTANCE_EDGES)
        if (
            StageId.VALIDATE_INSTANCE_EDGES in reusable
            and instance_result is not None
            and isinstance(instance_result.outcome, EdgeValidationOutcome)
            and instance_result.outcome.instance is not None
        ):
            instance = self.store.read_model(
                instance_result.outcome.instance.path,
                Instance,
                max_bytes=104_857_600,
            )
            self.manifest.instance_hash = instance.instance_hash
        elif boundary is not None and STAGE_ORDER.index(boundary) <= 2:
            self.manifest.instance_hash = None
        return ReconciliationResult(
            histories,
            reusable,
            boundary,
            tuple(dict.fromkeys(self.discarded_histories)),
        )

    def validate_compatibility(self) -> None:
        if run_config_hash(self.config) != self.manifest.run_config_hash:
            raise OperationalError(
                ErrorCode.INTEGRITY_ERROR,
                "Run configuration hash mismatch blocks reconciliation.",
            )

    def _is_integral(
        self,
        stage: StageId,
        result: StageResult,
        histories: dict[StageId, StageResult],
    ) -> bool:
        if result.status == "failed" or result.status == "cancelled":
            return False
        if result.status == "skipped":
            skip = result.attempts[-1].skip
            if (
                skip is None
                or skip.kind != "own"
                or stage
                not in {
                    StageId.RUN_EXACT_METHOD,
                    StageId.RUN_REFERENCE_METHOD,
                }
            ):
                return False
        if not all(self.store.verify(reference) for reference in result.artifacts):
            return False
        try:
            return self._validate_stage(stage, result, histories)
        except (OperationalError, ValueError):
            return False

    def _validate_stage(
        self,
        stage: StageId,
        result: StageResult,
        histories: dict[StageId, StageResult],
    ) -> bool:
        validators: dict[StageId, Callable[[StageResult, dict[StageId, StageResult]], bool]] = {
            StageId.DEFINE_EXPERIMENT: self._validate_definition,
            StageId.LOAD_OR_GENERATE_INSTANCE: self._validate_candidate,
            StageId.VALIDATE_INSTANCE_EDGES: self._validate_edges,
            StageId.VALIDATE_LINEAR_FOREST: self._validate_forest,
            StageId.ANALYZE_STRUCTURE: self._validate_analysis,
            StageId.RUN_EXACT_METHOD: self._validate_counting,
            StageId.RUN_REFERENCE_METHOD: self._validate_counting,
            StageId.COMPARE_RESULTS: self._validate_comparison,
            StageId.COLLECT_METRICS: self._validate_metrics,
            StageId.EXPORT_REPORT: self._validate_report,
        }
        return validators[stage](result, histories)

    def _validate_definition(
        self, result: StageResult, _histories: dict[StageId, StageResult]
    ) -> bool:
        outcome = result.outcome
        if not isinstance(outcome, DefinitionOutcome):
            return False
        experiment = self.store.read_model(
            f"experiments/{self.manifest.experiment_id}.json",
            ExperimentConfig,
            max_bytes=104_857_600,
        )
        return outcome.config_hash == self.manifest.run_config_hash and experiment == self.config

    def _validate_candidate(
        self, result: StageResult, _histories: dict[StageId, StageResult]
    ) -> bool:
        outcome = result.outcome
        return (
            isinstance(outcome, CandidateOutcome)
            and self._only_artifacts(result, outcome.candidate.path)
            and self.store.verify(outcome.candidate)
        )

    def _validate_edges(self, result: StageResult, _histories: dict[StageId, StageResult]) -> bool:
        outcome = result.outcome
        if not isinstance(outcome, EdgeValidationOutcome) or not outcome.validation.valid:
            return False
        if outcome.instance is None or not self._only_artifacts(result, outcome.instance.path):
            return False
        instance = self.store.read_model(outcome.instance.path, Instance, max_bytes=104_857_600)
        return (
            self.store.verify(outcome.instance)
            and instance.n == self.config.n
            and instance.instance_hash == instance_hash(instance.n, tuple(instance.edges))
        )

    @staticmethod
    def _validate_forest(result: StageResult, _histories: dict[StageId, StageResult]) -> bool:
        outcome = result.outcome
        return isinstance(outcome, ForestValidationOutcome) and outcome.validation.valid

    def _validate_analysis(
        self, result: StageResult, _histories: dict[StageId, StageResult]
    ) -> bool:
        outcome = result.outcome
        if not isinstance(outcome, StructureOutcome) or not self._only_artifacts(
            result, outcome.analysis.path
        ):
            return False
        instance = self.repository.load_artifact("instance.json", Instance)
        analysis = self.store.read_model(
            outcome.analysis.path, LinearForestAnalysis, max_bytes=104_857_600
        )
        return self.store.verify(outcome.analysis) and validate_analysis_integrity(
            instance.n, tuple(instance.edges), analysis
        )

    def _validate_counting(
        self, result: StageResult, _histories: dict[StageId, StageResult]
    ) -> bool:
        outcome = result.outcome
        reference = (
            outcome.result if isinstance(outcome, (ExactOutcome, ReferenceOutcome)) else None
        )
        if reference is None or not self._only_artifacts(result, reference.path):
            return False
        counting: CountingSuccess | CountingSkipped = TypeAdapter(CountingResult).validate_python(
            self.store.read_json_value(reference.path, max_bytes=10_485_760)
        )
        return (
            self.store.verify(reference)
            and counting.instance_hash == self._instance().instance_hash
            and counting.counting_convention == self.config.counting_convention
            and self._producer_is_compatible(result.stage, counting.engine)
        )

    def _validate_comparison(
        self, result: StageResult, _histories: dict[StageId, StageResult]
    ) -> bool:
        outcome = result.outcome
        if not isinstance(outcome, ComparisonOutcome) or not self._only_artifacts(
            result, outcome.result.path
        ):
            return False
        comparison = self.store.read_model(
            outcome.result.path, ComparisonResult, max_bytes=10_485_760
        )
        return (
            self.store.verify(outcome.result)
            and comparison.instance_hash == self._instance().instance_hash
            and comparison.counting_convention == self.config.counting_convention
        )

    @staticmethod
    def _validate_metrics(result: StageResult, histories: dict[StageId, StageResult]) -> bool:
        outcome = result.outcome
        if not isinstance(outcome, MetricsOutcome) or result.artifacts:
            return False
        for summary in outcome.stages:
            measured = histories.get(StageId(summary.stage))
            if measured is None:
                return False
            attempt = measured.attempts[-1]
            if (
                summary.attempt_number != attempt.number
                or summary.status != attempt.status
                or summary.termination != attempt.termination
                or summary.metrics != attempt.metrics
            ):
                return False
        return True

    def _validate_report(self, result: StageResult, _histories: dict[StageId, StageResult]) -> bool:
        outcome = result.outcome
        if not isinstance(outcome, ReportOutcome):
            return False
        if {item.path for item in result.artifacts} != {
            outcome.json_report.path,
            outcome.markdown_report.path,
        }:
            return False
        report = self.store.read_model(
            outcome.json_report.path, ReportSummary, max_bytes=104_857_600
        )
        expected = ReportBuilder(self.repository).build(self.manifest.status)
        markdown = self.store.read_bytes(outcome.markdown_report.path, max_bytes=104_857_600)
        return (
            report == expected
            and self.store.verify(outcome.json_report)
            and self.store.verify(outcome.markdown_report)
            and self.store.read_bytes(outcome.json_report.path, max_bytes=104_857_600)
            == render_json(expected)
            and markdown == render_markdown(expected).encode("utf-8")
        )

    @staticmethod
    def _only_artifacts(result: StageResult, path: str) -> bool:
        return [item.path for item in result.artifacts] == [path]

    def _instance(self) -> Instance:
        return self.repository.load_artifact("instance.json", Instance)

    def _producer_is_compatible(self, stage: StageId, producer: object) -> bool:
        if stage == StageId.RUN_EXACT_METHOD:
            from tesis_proyect.engines.exact import EXACT_PRODUCER

            return producer == EXACT_PRODUCER
        return producer == self.manifest.versions.reference
