"""Transport-neutral execution observations shared by application layers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from tesis_proyect.models.common import ArtifactRef, StructuredError
from tesis_proyect.models.enums import RunStatus, StageId, StageTerminalStatus
from tesis_proyect.models.protocols import (
    CancellationAcceptedPayload,
    DiagnosticPayload,
    EventEnvelope,
    InterruptionPayload,
    ReportExportedPayload,
    RunCreatedPayload,
    RunningPayload,
    RunResumedPayload,
    RunTerminalPayload,
    StageStartedPayload,
    StageTerminalPayload,
)


@dataclass(frozen=True)
class CommandStarted:
    command: str


@dataclass(frozen=True)
class CommandFinished:
    command: str
    outcome: Literal["success", "error"]
    run_id: str | None = None
    experiment_id: str | None = None
    run_status: RunStatus | None = None


@dataclass(frozen=True)
class RunCreated:
    run_id: str
    timestamp: str


@dataclass(frozen=True)
class RunStarted:
    run_id: str
    timestamp: str


@dataclass(frozen=True)
class RunResumed:
    run_id: str
    timestamp: str
    from_stage: StageId


@dataclass(frozen=True)
class RunInterruptionDetected:
    run_id: str
    timestamp: str
    stage: StageId | None


@dataclass(frozen=True)
class StageStarted:
    run_id: str
    timestamp: str
    stage: StageId
    ordinal: int
    total_stages: int
    attempt: int


@dataclass(frozen=True)
class StageProgress:
    run_id: str
    stage: StageId
    completed: int
    total: int | None

    def __post_init__(self) -> None:
        if self.completed < 0:
            raise ValueError("completed progress must be non-negative")
        if self.total is not None and (self.total < 0 or self.completed > self.total):
            raise ValueError("completed progress must not exceed total")


@dataclass(frozen=True)
class StageFinished:
    run_id: str
    timestamp: str
    stage: StageId
    ordinal: int
    total_stages: int
    attempt: int
    status: StageTerminalStatus
    result: ArtifactRef


@dataclass(frozen=True)
class RunFinished:
    run_id: str
    timestamp: str
    status: RunStatus


@dataclass(frozen=True)
class CancellationRegistered:
    run_id: str
    timestamp: str
    requested_at: str


@dataclass(frozen=True)
class ReportExported:
    run_id: str
    timestamp: str
    json_report: ArtifactRef
    markdown_report: ArtifactRef


@dataclass(frozen=True)
class DiagnosticRaised:
    run_id: str | None
    timestamp: str
    error: StructuredError


type ExecutionNotification = (
    CommandStarted
    | CommandFinished
    | RunCreated
    | RunStarted
    | RunResumed
    | RunInterruptionDetected
    | StageStarted
    | StageProgress
    | StageFinished
    | RunFinished
    | CancellationRegistered
    | ReportExported
    | DiagnosticRaised
)


class ExecutionObserver(Protocol):
    def notify(self, notification: ExecutionNotification) -> None: ...


class NullExecutionObserver:
    def notify(self, notification: ExecutionNotification) -> None:
        del notification


class CompositeExecutionObserver:
    def __init__(self, *observers: ExecutionObserver) -> None:
        self.observers = observers

    def notify(self, notification: ExecutionNotification) -> None:
        for observer in self.observers:
            observer.notify(notification)


class BestEffortExecutionObserver:
    def __init__(self, observer: ExecutionObserver) -> None:
        self.observer = observer

    def notify(self, notification: ExecutionNotification) -> None:
        try:
            self.observer.notify(notification)
        except Exception:
            return


class PublicEventObserver:
    """Map neutral execution notifications to the stable public event contract."""

    def __init__(self, emit: Callable[[EventEnvelope], None]) -> None:
        self.emit = emit

    def notify(self, notification: ExecutionNotification) -> None:
        event = self._event(notification)
        if event is not None:
            self.emit(event)

    def _event(self, notification: ExecutionNotification) -> EventEnvelope | None:
        event = self._run_event(notification)
        if event is not None:
            return event
        event = self._stage_event(notification)
        if event is not None:
            return event
        return self._other_event(notification)

    def _run_event(self, notification: ExecutionNotification) -> EventEnvelope | None:
        if isinstance(notification, RunCreated):
            return EventEnvelope(
                schema_version="1.0.0",
                event="run_created",
                run_id=notification.run_id,
                timestamp=notification.timestamp,
                stage=None,
                payload=RunCreatedPayload(status="created"),
            )
        if isinstance(notification, RunStarted):
            return EventEnvelope(
                schema_version="1.0.0",
                event="run_started",
                run_id=notification.run_id,
                timestamp=notification.timestamp,
                stage=None,
                payload=RunningPayload(status="running"),
            )
        if isinstance(notification, RunResumed):
            return EventEnvelope(
                schema_version="1.0.0",
                event="run_resumed",
                run_id=notification.run_id,
                timestamp=notification.timestamp,
                stage=None,
                payload=RunResumedPayload(status="running", from_stage=notification.from_stage),
            )
        if isinstance(notification, RunInterruptionDetected):
            return EventEnvelope(
                schema_version="1.0.0",
                event="run_interruption_detected",
                run_id=notification.run_id,
                timestamp=notification.timestamp,
                stage=None,
                payload=InterruptionPayload(status="running", stage=notification.stage),
            )
        if isinstance(notification, RunFinished):
            return EventEnvelope(
                schema_version="1.0.0",
                event="run_terminal",
                run_id=notification.run_id,
                timestamp=notification.timestamp,
                stage=None,
                payload=RunTerminalPayload(
                    status=cast(
                        Literal["completed", "failed", "cancelled"],
                        notification.status.value,
                    )
                ),
            )
        return None

    def _stage_event(self, notification: ExecutionNotification) -> EventEnvelope | None:
        if isinstance(notification, StageStarted):
            return EventEnvelope(
                schema_version="1.0.0",
                event="stage_started",
                run_id=notification.run_id,
                timestamp=notification.timestamp,
                stage=notification.stage,
                payload=StageStartedPayload(status="running", attempt=notification.attempt),
            )
        if isinstance(notification, StageFinished):
            return EventEnvelope(
                schema_version="1.0.0",
                event="stage_terminal",
                run_id=notification.run_id,
                timestamp=notification.timestamp,
                stage=notification.stage,
                payload=StageTerminalPayload(
                    status=notification.status,
                    attempt=notification.attempt,
                    result=notification.result,
                ),
            )
        return None

    def _other_event(self, notification: ExecutionNotification) -> EventEnvelope | None:
        if isinstance(notification, CancellationRegistered):
            return EventEnvelope(
                schema_version="1.0.0",
                event="cancellation_accepted",
                run_id=notification.run_id,
                timestamp=notification.timestamp,
                stage=None,
                payload=CancellationAcceptedPayload(
                    status="accepted", requested_at=notification.requested_at
                ),
            )
        if isinstance(notification, ReportExported):
            return EventEnvelope(
                schema_version="1.0.0",
                event="report_exported",
                run_id=notification.run_id,
                timestamp=notification.timestamp,
                stage=None,
                payload=ReportExportedPayload(
                    status="success",
                    json_report=notification.json_report,
                    markdown_report=notification.markdown_report,
                ),
            )
        if isinstance(notification, DiagnosticRaised):
            return EventEnvelope(
                schema_version="1.0.0",
                event="diagnostic",
                run_id=notification.run_id,
                timestamp=notification.timestamp,
                stage=None,
                payload=DiagnosticPayload(error=notification.error),
            )
        return None
