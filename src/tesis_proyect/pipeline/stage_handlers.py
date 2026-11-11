from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast
from uuid import uuid4

from tesis_proyect.domain.analysis import analyze_linear_forest
from tesis_proyect.domain.hashing import instance_hash, run_config_hash
from tesis_proyect.domain.validation import validate_edges, validate_linear_forest
from tesis_proyect.engines.exact import EXACT_PRODUCER
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import ProducerRef
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import (
    STAGE_ORDER,
    ComparisonStatus,
    ErrorCode,
    RunStatus,
    StageId,
)
from tesis_proyect.models.execution import (
    Instance,
    InstanceCandidate,
    MeasuredStageId,
    RunManifest,
    StageMetricSummary,
)
from tesis_proyect.models.protocols import WorkerLimits, WorkerRequest, WorkerResponse
from tesis_proyect.models.scientific import ComparisonResult
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
from tesis_proyect.observation import (
    ExecutionObserver,
    ReportExported,
    StageProgress,
)
from tesis_proyect.persistence.run_repository import RunRepository
from tesis_proyect.pipeline.sources import materialize_candidate
from tesis_proyect.pipeline.stage_journal import StageJournal, Termination
from tesis_proyect.reporting.builder import ReportBuilder
from tesis_proyect.reporting.render import render_json, render_markdown
from tesis_proyect.runner.workers import WorkerExecutionFailure

type WorkerExecutor = Callable[..., tuple[WorkerResponse, Termination]]


class StageHandlers:
    """Concrete Increment 1 stage actions; orchestration stays elsewhere."""

    def __init__(
        self,
        repository: RunRepository,
        config: ExperimentConfig,
        manifest: RunManifest,
        results: dict[StageId, StageResult],
        journal: StageJournal,
        observer: ExecutionObserver,
        *,
        clock: Callable[[], str],
        worker_executor: WorkerExecutor,
        cancellation_connection: Any,
        reuse: Callable[[StageId], bool],
    ) -> None:
        self.repository = repository
        self.store = repository.store
        self.config = config
        self.manifest = manifest
        self.results = results
        self.journal = journal
        self.observer = observer
        self.clock = clock
        self.worker_executor = worker_executor
        self.cancellation_connection = cancellation_connection
        self.reuse = reuse

    def define(self) -> None:
        stage = StageId.DEFINE_EXPERIMENT
        if self.reuse(stage):
            return
        self.journal.start(stage)
        if run_config_hash(self.config) != self.manifest.run_config_hash:
            raise OperationalError(ErrorCode.INTEGRITY_ERROR, "Run configuration hash mismatch.")
        experiment = self.store.read_model(
            f"experiments/{self.manifest.experiment_id}.json",
            ExperimentConfig,
            max_bytes=104_857_600,
        )
        if experiment != self.config:
            raise OperationalError(
                ErrorCode.INTEGRITY_ERROR, "Experiment differs from immutable run config."
            )
        self.journal.success(
            stage, DefinitionOutcome(kind="definition", config_hash=self.manifest.run_config_hash)
        )

    def candidate(self) -> None:
        stage = StageId.LOAD_OR_GENERATE_INSTANCE
        if self.reuse(stage):
            return
        self.journal.start(stage)
        candidate = materialize_candidate(self.config, self.store)
        reference = self.store.write_json(
            self.repository.layout.artifact("instance_candidate.json"), candidate
        )
        self.journal.success(
            stage,
            CandidateOutcome(kind="candidate", candidate=reference),
            (reference,),
        )

    def edges(self) -> ErrorCode | None:
        stage = StageId.VALIDATE_INSTANCE_EDGES
        if self.reuse(stage):
            return None
        self.journal.start(stage)
        candidate = self.repository.load_artifact("instance_candidate.json", InstanceCandidate)
        validation = validate_edges(candidate.n, candidate.edge_data)
        if validation.edges is None:
            diagnostic = validation.result.errors[0]
            self.journal.failed(
                stage,
                diagnostic.code,
                diagnostic.message,
                outcome=EdgeValidationOutcome(
                    kind="edge_validation", validation=validation.result, instance=None
                ),
            )
            return diagnostic.code
        digest = instance_hash(candidate.n, validation.edges)
        instance = Instance(
            schema_version="1.0.0",
            n=candidate.n,
            vertex_base=1,
            edges=list(validation.edges),
            source_metadata=candidate.source_metadata,
            instance_hash=digest,
        )
        reference = self.store.write_json(
            self.repository.layout.artifact("instance.json"), instance
        )
        self.manifest.instance_hash = digest
        self.journal.success(
            stage,
            EdgeValidationOutcome(
                kind="edge_validation", validation=validation.result, instance=reference
            ),
            (reference,),
        )
        self.repository.workspace.resolve(
            self.repository.layout.artifact("instance_candidate.json"), must_exist=True
        ).unlink()
        return None

    def forest(self) -> ErrorCode | None:
        stage = StageId.VALIDATE_LINEAR_FOREST
        if self.reuse(stage):
            return None
        self.journal.start(stage)
        instance = self.instance()
        validation = validate_linear_forest(instance.n, tuple(instance.edges))
        outcome = ForestValidationOutcome(kind="forest_validation", validation=validation)
        if not validation.valid:
            diagnostic = validation.errors[0]
            self.journal.failed(stage, diagnostic.code, diagnostic.message, outcome=outcome)
            return diagnostic.code
        self.journal.success(stage, outcome)
        return None

    def analysis(self) -> None:
        stage = StageId.ANALYZE_STRUCTURE
        if self.reuse(stage):
            return
        self.journal.start(stage)
        instance = self.instance()
        analysis = analyze_linear_forest(instance.n, tuple(instance.edges))
        reference = self.store.write_json(
            self.repository.layout.artifact("structure_summary.json"), analysis
        )
        self.journal.success(
            stage,
            StructureOutcome(kind="structure_analysis", analysis=reference),
            (reference,),
        )

    def exact(self) -> ErrorCode | None:
        return self.count(
            StageId.RUN_EXACT_METHOD,
            EXACT_PRODUCER,
            "exact_result.json",
        )

    def reference(self) -> ErrorCode | None:
        return self.count(
            StageId.RUN_REFERENCE_METHOD,
            ProducerRef(id="bruteforce-python", version="1"),
            "reference_result.json",
        )

    def count(
        self,
        stage: StageId,
        producer: ProducerRef,
        filename: str,
    ) -> ErrorCode | None:
        if self.reuse(stage):
            return None
        request = self.worker_request(stage, producer)
        self.journal.start(stage)
        try:
            response, termination = self.worker_executor(
                request,
                timeout_ms=request.limits.timeout_ms,
                cancellation_grace_ms=self.config.integer_limits.cancellation_grace_ms,
                cancellation_connection=self.cancellation_connection,
                progress_callback=self.progress_callback(stage, request),
            )
        except OperationalError as exc:
            failure_termination: Termination = (
                exc.termination if isinstance(exc, WorkerExecutionFailure) else "forced"
            )
            if exc.code == ErrorCode.RUN_CANCELLED:
                self.journal.cancelled(stage, str(exc), termination=failure_termination)
            else:
                details = exc.details if isinstance(exc, WorkerExecutionFailure) else None
                self.journal.failed(
                    stage,
                    exc.code,
                    str(exc),
                    details=details,
                    termination=failure_termination,
                )
            return exc.code
        if response.status == "failed" or response.result is None:
            code = response.error.code if response.error else ErrorCode.WORKER_PROTOCOL_ERROR
            message = response.error.message if response.error else "Worker failed."
            if code == ErrorCode.RUN_CANCELLED:
                self.journal.cancelled(stage, message, termination=termination)
            else:
                self.journal.failed(
                    stage,
                    code,
                    message,
                    details=response.error.details if response.error else None,
                    termination=termination,
                )
            return code
        relative = self.repository.layout.artifact(filename)
        reference = self.store.write_json(relative, response.result)
        outcome: ExactOutcome | ReferenceOutcome
        if stage == StageId.RUN_EXACT_METHOD:
            outcome = ExactOutcome(kind="exact_counting", result=reference)
        else:
            outcome = ReferenceOutcome(kind="reference_counting", result=reference)
        if response.status == "skipped":
            assert response.result.skip is not None
            self.journal.skipped(
                stage,
                response.result.skip,
                outcome,
                (reference,),
                response.metrics,
                termination,
            )
        else:
            self.journal.success(stage, outcome, (reference,), response.metrics, termination)
        return None

    def comparison(self, method_failure: ErrorCode | None) -> ErrorCode | None:
        stage = StageId.COMPARE_RESULTS
        if self.reuse(stage):
            return None
        if method_failure is not None:
            self.journal.dependency_skip(stage, method_failure)
            return None
        self.journal.start(stage)
        try:
            exact = self.repository.load_counting("exact_result.json")
            reference = self.repository.load_counting("reference_result.json")
            instance = self.instance()
        except (OperationalError, ValueError):
            self.journal.failed(
                stage,
                ErrorCode.INTEGRITY_ERROR,
                "Counting evidence is unreadable or violates its public model.",
            )
            return ErrorCode.INTEGRITY_ERROR
        if (
            exact.instance_hash != instance.instance_hash
            or reference.instance_hash != instance.instance_hash
            or exact.counting_convention != self.config.counting_convention
            or reference.counting_convention != self.config.counting_convention
            or exact.engine != EXACT_PRODUCER
            or reference.engine != self.manifest.versions.reference
        ):
            self.journal.failed(
                stage,
                ErrorCode.INTEGRITY_ERROR,
                "Counting results have incompatible instance, convention, or provenance.",
            )
            return ErrorCode.INTEGRITY_ERROR
        if exact.status == "success" and reference.status == "success":
            status = (
                ComparisonStatus.MATCH
                if exact.value == reference.value
                else ComparisonStatus.MISMATCH
            )
            reason = None
        else:
            status = ComparisonStatus.NOT_APPLICABLE
            skipped = exact if exact.status == "skipped" else reference
            reason = skipped.skip
        comparison = ComparisonResult(
            schema_version="1.0.0",
            status=status,
            value_exact=exact.value,
            value_reference=reference.value,
            exact=exact.engine,
            reference=reference.engine,
            counting_convention=self.config.counting_convention,
            reason=reason,
            instance_hash=instance.instance_hash,
        )
        artifact = self.store.write_json(
            self.repository.layout.artifact("comparison_result.json"), comparison
        )
        self.journal.success(
            stage, ComparisonOutcome(kind="comparison", result=artifact), (artifact,)
        )
        return None

    def metrics(self) -> None:
        stage = StageId.COLLECT_METRICS
        if self.reuse(stage):
            return
        self.journal.start(stage)
        summaries: list[StageMetricSummary] = []
        for measured_stage in STAGE_ORDER[:8]:
            attempt = self.results[measured_stage].attempts[-1]
            summaries.append(
                StageMetricSummary(
                    stage=cast(MeasuredStageId, measured_stage.value),
                    attempt_number=attempt.number,
                    status=attempt.status,
                    termination=attempt.termination,
                    metrics=attempt.metrics,
                )
            )
        self.journal.success(
            stage,
            MetricsOutcome(kind="metrics_collection", stages=summaries),
        )

    def report(self, final: RunStatus) -> None:
        stage = StageId.EXPORT_REPORT
        if self.reuse(stage):
            return
        self.journal.start(stage)
        report = ReportBuilder(self.repository).build(final)
        json_ref = self.store.write_bytes(
            self.repository.layout.report("result.json"),
            render_json(report),
        )
        markdown_ref = self.store.write_bytes(
            self.repository.layout.report("report.md"),
            render_markdown(report).encode("utf-8"),
        )
        self.journal.success(
            stage,
            ReportOutcome(kind="report_export", json_report=json_ref, markdown_report=markdown_ref),
            (json_ref, markdown_ref),
        )
        self.observer.notify(
            ReportExported(
                run_id=self.manifest.run_id,
                timestamp=self.clock(),
                json_report=json_ref,
                markdown_report=markdown_ref,
            )
        )

    def worker_request(self, stage: StageId, producer: ProducerRef) -> WorkerRequest:
        timeout = (
            self.config.integer_limits.exact_timeout_ms
            if stage == StageId.RUN_EXACT_METHOD
            else self.config.integer_limits.reference_timeout_ms
        )
        return WorkerRequest(
            schema_version="1.0.0",
            request_id=str(uuid4()),
            run_id=self.manifest.run_id,
            stage=(
                "run_exact_method" if stage == StageId.RUN_EXACT_METHOD else "run_reference_method"
            ),
            instance=self.instance(),
            producer=producer,
            limits=WorkerLimits(
                timeout_ms=timeout,
                max_message_bytes=self.config.integer_limits.worker_max_message_bytes,
                reference_max_n=self.config.integer_limits.reference_max_n,
            ),
            counting_convention=self.config.counting_convention,
        )

    def progress_callback(
        self, stage: StageId, request: WorkerRequest
    ) -> Callable[[int, int], None]:
        def notify(completed: int, total: int) -> None:
            self.observer.notify(
                StageProgress(
                    run_id=self.manifest.run_id,
                    stage=stage,
                    completed=completed,
                    total=total,
                )
            )

        return notify

    def instance(self) -> Instance:
        return self.repository.load_artifact("instance.json", Instance)
