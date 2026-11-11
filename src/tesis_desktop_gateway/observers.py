from __future__ import annotations

from typing import Protocol

from tesis_proyect.observation import StageFinished, StageProgress, StageStarted


class EventSink(Protocol):
    domain_run_id: str

    def emit(self, event: str, data: dict[str, object]) -> None: ...


class GatewayGroupedObserver:
    def __init__(self, sink: EventSink) -> None:
        self.sink = sink

    def generation_started(self, total: int) -> None:
        self.sink.emit(
            "generation_started",
            {"domain_run_id": self.sink.domain_run_id, "total": total},
        )

    def generation_progress(
        self, completed: int, total: int, valid_selections: int | None = None
    ) -> None:
        self.sink.emit(
            "generation_progress",
            {
                "domain_run_id": self.sink.domain_run_id,
                "completed": completed,
                "total": total,
                "valid_selections": valid_selections,
            },
        )

    def core_case_started(
        self,
        ordinal: int,
        description: str,
        core_run_id: str | None = None,
        design_id: str | None = None,
    ) -> None:
        if core_run_id is None:
            return
        self.sink.emit(
            "core_case_started",
            {
                "domain_run_id": self.sink.domain_run_id,
                "ordinal": ordinal,
                "description": description,
                "core_run_id": core_run_id,
                "design_id": design_id,
            },
        )


class GatewayCoreObserver:
    def __init__(self, sink: EventSink) -> None:
        self.sink = sink

    def notify(self, notification: object) -> None:
        if isinstance(notification, StageProgress):
            completed, total = notification.completed, notification.total
        elif isinstance(notification, StageStarted):
            completed, total = 0, None
        elif isinstance(notification, StageFinished):
            completed, total = 1, 1
        else:
            return
        self.sink.emit(
            "core_progress",
            {
                "domain_run_id": self.sink.domain_run_id,
                "core_run_id": notification.run_id,
                "stage": notification.stage.value,
                "completed": completed,
                "total": total,
            },
        )
