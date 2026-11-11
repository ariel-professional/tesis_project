from __future__ import annotations

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import Cancellation
from tesis_proyect.models.enums import (
    ErrorCode,
    RunStatus,
    StageId,
)
from tesis_proyect.models.execution import RunManifest
from tesis_proyect.models.factories import structured_error
from tesis_proyect.models.protocols import ControlRequest, ControlResponse
from tesis_proyect.observation import (
    CancellationRegistered,
    ExecutionObserver,
    NullExecutionObserver,
    RunInterruptionDetected,
)
from tesis_proyect.persistence.run_repository import RunRepository
from tesis_proyect.persistence.workspace import Workspace
from tesis_proyect.pipeline.orchestrator import PipelineCoordinator
from tesis_proyect.runner.clock import utc_timestamp
from tesis_proyect.runner.control_transport import ControlServer, send_control
from tesis_proyect.runner.locking import RunExecutionLock, WorkspaceWriteLock


class RunOperations:
    def __init__(
        self,
        workspace: Workspace,
        *,
        observer: ExecutionObserver | None = None,
    ) -> None:
        self.workspace = workspace
        self.observer = observer or NullExecutionObserver()

    def run(self, run_id: str) -> RunManifest:
        repository = RunRepository(self.workspace, run_id)
        run_lock = RunExecutionLock(self.workspace.resolve(repository.layout.lock, must_exist=True))
        runner: PipelineCoordinator | None = None
        with WorkspaceWriteLock(self.workspace.root / ".domain-write.lock"):
            manifest = repository.load_manifest()
            if manifest.status != RunStatus.CREATED:
                raise OperationalError(
                    ErrorCode.RUN_STATE_INVALID, "Only a created run can be run."
                )
            run_lock.acquire()
            try:
                runner = PipelineCoordinator(self.workspace, run_id, observer=self.observer)
                runner.activate()
            except BaseException:
                run_lock.release()
                raise
        try:
            assert runner is not None
            with self.control_server(runner):
                return runner.run(activated=True)
        finally:
            run_lock.release()

    def resume(self, run_id: str) -> RunManifest:
        repository = RunRepository(self.workspace, run_id)
        run_lock = RunExecutionLock(self.workspace.resolve(repository.layout.lock, must_exist=True))
        runner: PipelineCoordinator | None = None
        no_work_result: RunManifest | None = None
        with WorkspaceWriteLock(self.workspace.root / ".domain-write.lock"):
            run_lock.acquire()
            try:
                manifest = repository.load_manifest()
                if manifest.status not in {
                    RunStatus.COMPLETED,
                    RunStatus.FAILED,
                    RunStatus.RUNNING,
                }:
                    raise OperationalError(
                        ErrorCode.RUN_STATE_INVALID,
                        "Resume accepts completed, failed, or interrupted running runs only.",
                    )
                runner = PipelineCoordinator(self.workspace, run_id, observer=self.observer)
                runner.validate_resume_compatibility()
                if manifest.status == RunStatus.RUNNING:
                    running = runner.active_stage()
                    if running is not None:
                        self._emit_interruption(run_id, running)
                        runner.mark_interrupted(running)
                if not runner.prepare_resume():
                    no_work_result = runner.manifest
                    runner.close()
                    runner = None
                else:
                    runner.activate()
            except BaseException:
                if runner is not None:
                    runner.close()
                run_lock.release()
                raise
        if no_work_result is not None:
            run_lock.release()
            return no_work_result
        try:
            assert runner is not None
            with self.control_server(runner):
                return runner.run(resumed=True, activated=True)
        except Exception:
            assert runner is not None
            runner.close()
            raise
        finally:
            run_lock.release()

    def cancel(self, request: ControlRequest) -> ControlResponse:
        repository = RunRepository(self.workspace, request.run_id)
        manifest = repository.load_manifest()
        terminal = self._terminal_response(request, manifest)
        if terminal is not None:
            return terminal
        lock = RunExecutionLock(self.workspace.resolve(repository.layout.lock, must_exist=True))
        try:
            lock.acquire()
        except OperationalError as exc:
            if exc.code != ErrorCode.RUN_ALREADY_ACTIVE:
                raise
            return self._send_active_cancellation(repository, request)
        try:
            return self._cancel_under_lock(repository, request)
        finally:
            lock.release()

    def _send_active_cancellation(
        self, repository: RunRepository, request: ControlRequest
    ) -> ControlResponse:
        config = repository.load_config()
        try:
            return send_control(
                self.workspace.root,
                request,
                connect_timeout_ms=config.integer_limits.control_connect_timeout_ms,
                response_timeout_ms=config.integer_limits.control_response_timeout_ms,
                max_bytes=config.integer_limits.control_max_message_bytes,
            )
        except OperationalError:
            terminal = self._terminal_response(request, repository.load_manifest())
            if terminal is not None:
                return terminal
            raise

    def _cancel_under_lock(
        self, repository: RunRepository, request: ControlRequest
    ) -> ControlResponse:
        manifest = repository.load_manifest()
        terminal = self._terminal_response(request, manifest)
        if terminal is not None:
            return terminal
        runner = PipelineCoordinator(self.workspace, request.run_id, observer=self.observer)
        try:
            if manifest.status == RunStatus.RUNNING:
                running = runner.active_stage()
                self._emit_interruption(request.run_id, running)
                if running is not None:
                    runner.mark_interrupted(running)
            cancellation = Cancellation(
                requested_at=request.requested_at,
                origin=request.origin,
                reason=request.reason,
            )
            first = runner.manifest.cancellation is None
            if first:
                runner.register_cancellation(cancellation)
                self._emit_cancellation(request.run_id, cancellation)
            runner.cancel_now(cancellation)
            return ControlResponse(
                schema_version="1.0.0",
                request_id=request.request_id,
                run_id=request.run_id,
                status="accepted" if first else "already_registered",
                cancellation=runner.manifest.cancellation,
                error=None,
            )
        finally:
            runner.close()

    @staticmethod
    def _terminal_response(
        request: ControlRequest, manifest: RunManifest
    ) -> ControlResponse | None:
        if manifest.status not in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
            return None
        return ControlResponse(
            schema_version="1.0.0",
            request_id=request.request_id,
            run_id=request.run_id,
            status="terminal",
            cancellation=manifest.cancellation,
            error=None,
        )

    def control_server(self, runner: PipelineCoordinator) -> ControlServer:
        def handle(request: ControlRequest) -> ControlResponse:
            if request.run_id != runner.run_id:
                return ControlResponse(
                    schema_version="1.0.0",
                    request_id=request.request_id,
                    run_id=request.run_id,
                    status="rejected",
                    cancellation=None,
                    error=structured_error(
                        ErrorCode.RUN_STATE_INVALID,
                        "Control run ID mismatch.",
                        recoverable=False,
                    ),
                )
            cancellation = Cancellation(
                requested_at=request.requested_at,
                origin=request.origin,
                reason=request.reason,
            )
            accepted = runner.register_cancellation(cancellation)
            if accepted:
                self._emit_cancellation(request.run_id, cancellation)
            return ControlResponse(
                schema_version="1.0.0",
                request_id=request.request_id,
                run_id=request.run_id,
                status="accepted" if accepted else "already_registered",
                cancellation=runner.manifest.cancellation,
                error=None,
            )

        return ControlServer(
            self.workspace.root,
            runner.run_id,
            handle,
            max_bytes=runner.config.integer_limits.control_max_message_bytes,
        )

    def _emit_cancellation(self, run_id: str, cancellation: Cancellation) -> None:
        self.observer.notify(
            CancellationRegistered(
                run_id=run_id,
                timestamp=utc_timestamp(),
                requested_at=cancellation.requested_at,
            )
        )

    def _emit_interruption(self, run_id: str, stage: StageId | None) -> None:
        self.observer.notify(
            RunInterruptionDetected(
                run_id=run_id,
                timestamp=utc_timestamp(),
                stage=stage,
            )
        )
