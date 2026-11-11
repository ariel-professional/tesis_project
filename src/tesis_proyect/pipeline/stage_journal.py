from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter_ns
from typing import Any, Literal

from tesis_proyect.models.common import (
    ArtifactRef,
    AttemptMetrics,
    StructuredError,
)
from tesis_proyect.models.enums import (
    STAGE_ORDER,
    ErrorCode,
    StageId,
    StageStatus,
    StageTerminalStatus,
)
from tesis_proyect.models.execution import (
    PipelineState,
    RunManifest,
    SkipCause,
    StageAttempt,
    StageState,
)
from tesis_proyect.models.factories import structured_error
from tesis_proyect.models.stages import (
    StageOutcome,
    StageResult,
)
from tesis_proyect.observation import (
    ExecutionObserver,
    StageFinished,
    StageStarted,
)
from tesis_proyect.persistence.run_repository import RunRepository

type Termination = Literal["not_applicable", "cooperative", "forced"]


@dataclass(frozen=True)
class StageDraft:
    status: StageTerminalStatus
    outcome: StageOutcome | None = None
    artifacts: tuple[ArtifactRef, ...] = ()
    error: StructuredError | None = None
    skip: SkipCause | None = None
    metrics: AttemptMetrics | None = None
    termination: Termination = "not_applicable"


class StageJournal:
    """Own stage transitions, attempt timing, and durable confirmation order."""

    def __init__(
        self,
        repository: RunRepository,
        manifest: RunManifest,
        pipeline: PipelineState,
        results: dict[StageId, StageResult],
        observer: ExecutionObserver,
        *,
        clock: Callable[[], str],
        write_manifest: Callable[[], None],
    ) -> None:
        self.repository = repository
        self.manifest = manifest
        self.pipeline = pipeline
        self.results = results
        self.observer = observer
        self.clock = clock
        self.write_manifest = write_manifest
        self._started: dict[StageId, tuple[str, int]] = {}

    def start(self, stage: StageId) -> None:
        state = self.state(stage)
        self._started[stage] = (self.clock(), perf_counter_ns())
        self.replace_state(stage, StageStatus.RUNNING, state.attempt_count, None)
        self.repository.write_pipeline(self.pipeline)
        self.observer.notify(
            StageStarted(
                run_id=self.manifest.run_id,
                timestamp=self.clock(),
                stage=stage,
                ordinal=self.ordinal(stage),
                total_stages=len(STAGE_ORDER),
                attempt=state.attempt_count + 1,
            )
        )

    def commit(self, stage: StageId, draft: StageDraft) -> StageResult:
        started, tick = self._started.pop(stage, (self.clock(), perf_counter_ns()))
        finished = self.clock()
        duration = (perf_counter_ns() - tick) // 1_000_000
        metrics = draft.metrics or AttemptMetrics(
            duration_ms=duration,
            worker_duration_ms=None,
            candidates_examined=None,
            peak_memory_bytes=None,
            producer=None,
        )
        if metrics.duration_ms != duration:
            metrics = metrics.model_copy(update={"duration_ms": duration})
        previous = self.previous_attempts(stage)
        attempt = StageAttempt(
            number=len(previous) + 1,
            started_at=started,
            finished_at=finished,
            duration_ms=duration,
            status=draft.status,
            error=draft.error,
            skip=draft.skip,
            metrics=metrics,
            termination=draft.termination,
        )
        attempts = [*previous, attempt]
        result = StageResult(
            schema_version="1.0.0",
            stage=stage,
            status=draft.status,
            attempts=attempts,
            started_at=started,
            finished_at=finished,
            duration_ms=duration,
            error=draft.error,
            artifacts=list(draft.artifacts),
            outcome=draft.outcome,
        )
        result_ref = self.repository.store.write_json(self.repository.layout.stage(stage), result)
        self.results[stage] = result
        self.replace_state(stage, StageStatus(draft.status.value), len(attempts), result_ref)
        self.repository.write_pipeline(self.pipeline)
        self.write_manifest()
        self.observer.notify(
            StageFinished(
                run_id=self.manifest.run_id,
                timestamp=self.clock(),
                stage=stage,
                ordinal=self.ordinal(stage),
                total_stages=len(STAGE_ORDER),
                attempt=len(attempts),
                status=draft.status,
                result=result_ref,
            )
        )
        return result

    def success(
        self,
        stage: StageId,
        outcome: StageOutcome,
        artifacts: tuple[ArtifactRef, ...] = (),
        metrics: AttemptMetrics | None = None,
        termination: Termination = "not_applicable",
    ) -> StageResult:
        return self.commit(
            stage,
            StageDraft(
                status=StageTerminalStatus.SUCCESS,
                outcome=outcome,
                artifacts=artifacts,
                metrics=metrics,
                termination=termination,
            ),
        )

    def failed(
        self,
        stage: StageId,
        code: ErrorCode,
        message: str,
        *,
        outcome: StageOutcome | None = None,
        details: dict[str, Any] | None = None,
        termination: Termination = "not_applicable",
    ) -> StageResult:
        return self.commit(
            stage,
            StageDraft(
                status=StageTerminalStatus.FAILED,
                outcome=outcome,
                error=structured_error(code, message, stage=stage, details=details),
                termination=termination,
            ),
        )

    def skipped(
        self,
        stage: StageId,
        skip: SkipCause,
        outcome: StageOutcome | None = None,
        artifacts: tuple[ArtifactRef, ...] = (),
        metrics: AttemptMetrics | None = None,
        termination: Termination = "not_applicable",
    ) -> StageResult:
        return self.commit(
            stage,
            StageDraft(
                status=StageTerminalStatus.SKIPPED,
                outcome=outcome,
                artifacts=artifacts,
                skip=skip,
                metrics=metrics,
                termination=termination,
            ),
        )

    def cancelled(
        self,
        stage: StageId,
        message: str,
        *,
        termination: Termination,
    ) -> StageResult:
        return self.commit(
            stage,
            StageDraft(
                status=StageTerminalStatus.CANCELLED,
                error=structured_error(
                    ErrorCode.RUN_CANCELLED,
                    message,
                    stage=stage,
                    recoverable=False,
                ),
                termination=termination,
            ),
        )

    def dependency_skip(self, stage: StageId, code: ErrorCode) -> StageResult:
        self.start(stage)
        return self.skipped(
            stage,
            SkipCause(
                kind="dependency",
                code=code,
                message=f"Dependency unavailable because of {code}.",
            ),
        )

    def pending_skip(self, stage: StageId, code: ErrorCode) -> StageResult:
        """Terminalize work that never started, without emitting StageStarted."""
        self._started[stage] = (self.clock(), perf_counter_ns())
        return self.skipped(
            stage,
            SkipCause(
                kind="dependency",
                code=code,
                message=f"Stage was not started because of {code}.",
            ),
        )

    def state(self, stage: StageId) -> StageState:
        return self.pipeline.ordered_stages[self.ordinal(stage) - 1]

    def replace_state(
        self,
        stage: StageId,
        status: StageStatus,
        attempts: int,
        result: ArtifactRef | None,
    ) -> None:
        index = self.ordinal(stage) - 1
        self.pipeline.ordered_stages[index] = StageState(
            ordinal=index + 1,
            stage=stage,
            status=status,
            attempt_count=attempts,
            result=result,
        )

    def previous_attempts(self, stage: StageId) -> list[StageAttempt]:
        result = self.results.get(stage)
        return [] if result is None else result.attempts

    @staticmethod
    def ordinal(stage: StageId) -> int:
        return STAGE_ORDER.index(stage) + 1
