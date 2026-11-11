from __future__ import annotations

import logging
import multiprocessing
import threading
from collections.abc import Callable
from logging.handlers import RotatingFileHandler

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import Cancellation
from tesis_proyect.models.enums import (
    ErrorCode,
    RunStatus,
    StageId,
    StageStatus,
)
from tesis_proyect.models.execution import (
    RunManifest,
)
from tesis_proyect.models.factories import structured_error
from tesis_proyect.models.stages import (
    StageResult,
)
from tesis_proyect.observation import (
    DiagnosticRaised,
    ExecutionObserver,
    NullExecutionObserver,
    RunFinished,
    RunResumed,
    RunStarted,
)
from tesis_proyect.persistence.run_repository import RunRepository
from tesis_proyect.persistence.workspace import Workspace
from tesis_proyect.pipeline.reconciliation import CheckpointReconciler
from tesis_proyect.pipeline.stage_handlers import StageHandlers
from tesis_proyect.pipeline.stage_journal import StageJournal
from tesis_proyect.runner.clock import utc_timestamp
from tesis_proyect.runner.workers import execute_worker


class PipelineCoordinator:
    def __init__(
        self,
        workspace: Workspace,
        run_id: str,
        *,
        clock: Callable[[], str] = utc_timestamp,
        observer: ExecutionObserver | None = None,
    ) -> None:
        self.workspace = workspace
        self.run_id = run_id
        self.repository = RunRepository(workspace, run_id)
        self.store = self.repository.store
        self.clock = clock
        self.observer = observer or NullExecutionObserver()
        self.config = self.repository.load_config()
        self.manifest = self.repository.load_manifest()
        self.pipeline = self.repository.load_pipeline()
        self.results: dict[StageId, StageResult] = {}
        self.reusable: set[StageId] = set()
        self.cancel_requested = threading.Event()
        context = multiprocessing.get_context("spawn")
        self._cancel_recv, self._cancel_send = context.Pipe(duplex=False)
        self._manifest_lock = threading.Lock()
        self._load_confirmed_results()
        self.journal = StageJournal(
            self.repository,
            self.manifest,
            self.pipeline,
            self.results,
            self.observer,
            clock=self.clock,
            write_manifest=self._write_manifest,
        )
        self.handlers = StageHandlers(
            self.repository,
            self.config,
            self.manifest,
            self.results,
            self.journal,
            self.observer,
            clock=self.clock,
            worker_executor=lambda *args, **kwargs: execute_worker(
                *args,
                **kwargs,
                diagnostic_callback=self._record_worker_diagnostic,
                debug=self.config.persistence.policy == "debug",
            ),
            cancellation_connection=self._cancel_recv,
            reuse=self._reuse,
        )
        self._configure_log()

    def _configure_log(self) -> None:
        path = self.workspace.resolve(self.repository.layout.runner_log)
        handler = RotatingFileHandler(
            path,
            maxBytes=self.config.integer_limits.runner_log_max_bytes,
            backupCount=self.config.integer_limits.runner_log_backup_count,
            encoding="utf-8",
        )
        self.logger = logging.getLogger(f"tesis_proyect.run.{self.run_id}")
        self.logger.handlers.clear()
        self.logger.propagate = False
        self.logger.setLevel(
            logging.DEBUG if self.config.persistence.policy == "debug" else logging.INFO
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(handler)

    def _record_worker_diagnostic(self, message: str) -> None:
        self.logger.error(message)

    def activate(self) -> None:
        """Persist the running state while a workspace-wide start lock is held."""

        self.manifest.status = RunStatus.RUNNING
        self._write_manifest()

    def run(self, *, resumed: bool = False, activated: bool = False) -> RunManifest:
        try:
            return self._run(resumed=resumed, activated=activated)
        finally:
            self.close()

    def _run(self, *, resumed: bool, activated: bool) -> RunManifest:
        if activated:
            if self.manifest.status != RunStatus.RUNNING:
                raise OperationalError(
                    ErrorCode.RUN_STATE_INVALID,
                    "The run was not activated before execution.",
                )
        else:
            self.activate()
        if resumed:
            from_stage = self._active_or_first_pending()
            self.observer.notify(
                RunResumed(run_id=self.run_id, timestamp=self.clock(), from_stage=from_stage)
            )
        else:
            self.observer.notify(RunStarted(run_id=self.run_id, timestamp=self.clock()))
        self.logger.info("Run started")
        blocking, cancelled = self._execute_validation_stages()
        if cancelled:
            return self.manifest
        method_failure, cancelled = self._execute_scientific_stages(blocking)
        if cancelled:
            return self.manifest
        return self._finish(blocking, method_failure)

    def _execute_validation_stages(self) -> tuple[ErrorCode | None, bool]:
        blocking: ErrorCode | None = None
        try:
            self.handlers.define()
            if self._stop_for_cancellation():
                return blocking, True
            self.handlers.candidate()
            if self._stop_for_cancellation():
                return blocking, True
            blocking = self.handlers.edges()
            if self._stop_for_cancellation():
                return blocking, True
            if blocking is None:
                blocking = self.handlers.forest()
                if self._stop_for_cancellation():
                    return blocking, True
        except OperationalError as exc:
            blocking = exc.code
            stage = self._active_or_first_pending()
            self.journal.failed(stage, exc.code, str(exc))
        return blocking, False

    def _execute_scientific_stages(
        self, blocking: ErrorCode | None
    ) -> tuple[ErrorCode | None, bool]:
        if blocking is None:
            self.handlers.analysis()
            if self._stop_for_cancellation():
                return None, True
            method_failure = self.handlers.exact()
            if self._stop_for_cancellation():
                return method_failure, True
            reference_failure = self.handlers.reference()
            if self._stop_for_cancellation():
                return method_failure or reference_failure, True
            method_failure = method_failure or reference_failure
            comparison_failure = self.handlers.comparison(method_failure)
            return method_failure or comparison_failure, False
        self._skip_blocked_stages(blocking)
        return None, False

    def _skip_blocked_stages(self, blocking: ErrorCode) -> None:
        for stage in (
            StageId.LOAD_OR_GENERATE_INSTANCE,
            StageId.VALIDATE_INSTANCE_EDGES,
            StageId.VALIDATE_LINEAR_FOREST,
            StageId.ANALYZE_STRUCTURE,
            StageId.RUN_EXACT_METHOD,
            StageId.RUN_REFERENCE_METHOD,
            StageId.COMPARE_RESULTS,
        ):
            if self.journal.state(stage).status == StageStatus.PENDING:
                self.journal.dependency_skip(stage, blocking)

    def _finish(self, blocking: ErrorCode | None, method_failure: ErrorCode | None) -> RunManifest:
        self.handlers.metrics()
        final = (
            RunStatus.FAILED
            if blocking is not None or method_failure is not None
            else RunStatus.COMPLETED
        )
        self.handlers.report(final)
        self.manifest.status = final
        self._write_manifest()
        self.observer.notify(RunFinished(run_id=self.run_id, timestamp=self.clock(), status=final))
        self.logger.info("Run finished with status %s", final)
        return self.manifest

    def close(self) -> None:
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)

    def _active_or_first_pending(self) -> StageId:
        running = next(
            (
                item.stage
                for item in self.pipeline.ordered_stages
                if item.status == StageStatus.RUNNING
            ),
            None,
        )
        if running is not None:
            return running
        return next(
            item.stage
            for item in self.pipeline.ordered_stages
            if item.status == StageStatus.PENDING
        )

    def _write_manifest(self) -> None:
        with self._manifest_lock:
            self.manifest.updated_at = self.clock()
            self.repository.write_manifest(self.manifest)

    def register_cancellation(self, cancellation: Cancellation) -> bool:
        with self._manifest_lock:
            if self.manifest.cancellation is not None:
                return False
            self.manifest.cancellation = cancellation
            self.manifest.updated_at = self.clock()
            self.repository.write_manifest(self.manifest)
        self.cancel_requested.set()
        self._cancel_send.send_bytes(b"\x01")
        return True

    def active_stage(self) -> StageId | None:
        return next(
            (
                state.stage
                for state in self.pipeline.ordered_stages
                if state.status == StageStatus.RUNNING
            ),
            None,
        )

    def mark_interrupted(self, stage: StageId) -> None:
        self.journal.failed(
            stage,
            ErrorCode.RUNNER_INTERRUPTED,
            "The previous runner was interrupted.",
        )

    def prepare_resume(self) -> bool:
        reconciliation = CheckpointReconciler(
            self.repository,
            self.config,
            self.manifest,
            self.pipeline,
        ).reconcile()
        self.results = reconciliation.histories
        self.reusable = reconciliation.reusable
        self.journal.results = self.results
        self.handlers.results = self.results
        for stage in reconciliation.discarded_histories:
            message = f"Corrupt StageResult history was discarded for {stage.value}."
            self.logger.warning(message)
            self.observer.notify(
                DiagnosticRaised(
                    run_id=self.run_id,
                    timestamp=self.clock(),
                    error=structured_error(
                        ErrorCode.INTEGRITY_ERROR,
                        message,
                        stage=stage,
                        recoverable=True,
                    ),
                )
            )
        if reconciliation.boundary is not None:
            self._discard_unconfirmed_artifacts(reconciliation.boundary)
        self.manifest.status = (
            RunStatus.COMPLETED if reconciliation.boundary is None else RunStatus.FAILED
        )
        self.repository.write_pipeline(self.pipeline)
        self._write_manifest()
        return reconciliation.boundary is not None

    def validate_resume_compatibility(self) -> None:
        CheckpointReconciler(
            self.repository,
            self.config,
            self.manifest,
            self.pipeline,
        ).validate_compatibility()

    def _discard_unconfirmed_artifacts(self, boundary: StageId) -> None:
        produced: dict[StageId, tuple[str, ...]] = {
            StageId.LOAD_OR_GENERATE_INSTANCE: ("artifacts/instance_candidate.json",),
            StageId.VALIDATE_INSTANCE_EDGES: ("artifacts/instance.json",),
            StageId.ANALYZE_STRUCTURE: ("artifacts/structure_summary.json",),
            StageId.RUN_EXACT_METHOD: ("artifacts/exact_result.json",),
            StageId.RUN_REFERENCE_METHOD: ("artifacts/reference_result.json",),
            StageId.COMPARE_RESULTS: ("artifacts/comparison_result.json",),
            StageId.EXPORT_REPORT: ("reports/result.json", "reports/report.md"),
        }
        boundary_index = list(StageId).index(boundary)
        for stage, names in produced.items():
            if list(StageId).index(stage) < boundary_index:
                continue
            for name in names:
                self.workspace.resolve(f"runs/{self.run_id}/{name}").unlink(missing_ok=True)

    def cancel_now(self, cancellation: Cancellation) -> RunManifest:
        created = self.manifest.status == RunStatus.CREATED
        self.register_cancellation(cancellation)
        self._cancel_remaining(created=created)
        return self.manifest

    def _stop_for_cancellation(self) -> bool:
        if not self.cancel_requested.is_set() and self.manifest.cancellation is None:
            return False
        self._cancel_remaining()
        return True

    def _cancel_remaining(self, *, created: bool = False) -> None:
        pending = [
            item.stage
            for item in self.pipeline.ordered_stages
            if item.status in {StageStatus.PENDING, StageStatus.RUNNING}
        ]
        if created:
            for stage in pending:
                self.journal.pending_skip(stage, ErrorCode.RUN_CANCELLED)
        elif pending:
            active = pending[0]
            if self.journal.state(active).status == StageStatus.PENDING:
                self.journal.start(active)
            self.journal.cancelled(
                active, "Run cancellation was requested.", termination="cooperative"
            )
            for stage in pending[1:]:
                self.journal.dependency_skip(stage, ErrorCode.RUN_CANCELLED)
        self.manifest.status = RunStatus.CANCELLED
        self._write_manifest()
        self.observer.notify(
            RunFinished(
                run_id=self.run_id,
                timestamp=self.clock(),
                status=RunStatus.CANCELLED,
            )
        )

    def _load_confirmed_results(self) -> None:
        reconciler = CheckpointReconciler(
            self.repository,
            self.config,
            self.manifest,
            self.pipeline,
        )
        self.results.update(reconciler.histories())
        for state in self.pipeline.ordered_stages:
            result = self.results.get(state.stage)
            if (
                result is not None
                and state.result is not None
                and self.store.verify(state.result)
                and result.status.value == state.status.value
            ):
                self.reusable.add(state.stage)

    def _reuse(self, stage: StageId) -> bool:
        state = self.journal.state(stage)
        if state.status == StageStatus.SUCCESS:
            return stage in self.reusable
        if state.status == StageStatus.SKIPPED and stage in self.reusable:
            result = self.results[stage]
            return bool(result.attempts[-1].skip and result.attempts[-1].skip.kind == "own")
        return False
