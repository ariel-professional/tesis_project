from __future__ import annotations

from io import StringIO

from tesis_domain_extensions.contracts.common import MAX_SAFE_JSON_INTEGER
from tesis_domain_extensions.terminal_adapter import DomainTerminalObserver
from tesis_proyect.models.common import ArtifactRef
from tesis_proyect.models.enums import RunStatus, StageId, StageTerminalStatus
from tesis_proyect.observation import (
    CommandStarted,
    RunCreated,
    RunFinished,
    RunResumed,
    RunStarted,
    StageFinished,
    StageProgress,
    StageStarted,
)


def test_domain_terminal_maps_run_stage_and_continuous_progress_notifications() -> None:
    observer = DomainTerminalObserver(stream=StringIO(), enabled=True)
    updates: list[tuple[str, int | None, int | None]] = []

    def record(
        description: str,
        *,
        completed: int | None = None,
        total: int | None = None,
    ) -> None:
        updates.append((description, completed, total))

    observer._update = record  # type: ignore[method-assign]
    timestamp = "2026-08-24T12:00:00.000Z"
    observer.notify(RunCreated(run_id="run", timestamp=timestamp))
    observer.notify(RunStarted(run_id="run", timestamp=timestamp))
    observer.notify(
        RunResumed(
            run_id="run",
            timestamp=timestamp,
            from_stage=StageId.RUN_EXACT_METHOD,
        )
    )
    observer.notify(
        StageStarted(
            run_id="run",
            timestamp=timestamp,
            stage=StageId.RUN_REFERENCE_METHOD,
            ordinal=7,
            total_stages=10,
            attempt=1,
        )
    )
    observer.notify(
        StageProgress(
            run_id="run",
            stage=StageId.RUN_REFERENCE_METHOD,
            completed=25,
            total=100,
        )
    )
    observer.notify(
        StageFinished(
            run_id="run",
            timestamp=timestamp,
            stage=StageId.RUN_REFERENCE_METHOD,
            ordinal=7,
            total_stages=10,
            attempt=1,
            status=StageTerminalStatus.SUCCESS,
            result=ArtifactRef(path="stages/07.json", sha256="sha256:" + "0" * 64, size_bytes=1),
        )
    )
    observer.notify(RunFinished(run_id="run", timestamp=timestamp, status=RunStatus.COMPLETED))
    observer.notify(CommandStarted(command="run"))

    assert len(updates) == 7
    assert updates[4][1:] == (25, 100)
    assert "referencia" in updates[4][0]
    assert all("Command" not in description for description, _, _ in updates)


def test_domain_terminal_is_silent_outside_tty_and_reuses_one_progress_region() -> None:
    silent_stream = StringIO()
    silent = DomainTerminalObserver(stream=silent_stream, enabled=False)
    silent.set_status("hidden")
    silent.notify(RunCreated(run_id="run", timestamp="2026-08-24T12:00:00.000Z"))
    silent.close()
    assert silent_stream.getvalue() == ""

    stream = StringIO()
    observer = DomainTerminalObserver(stream=stream, enabled=True)
    observer.set_status("Preparando…")
    first_progress = observer.progress
    observer.notify(
        StageProgress(
            run_id="run",
            stage=StageId.RUN_EXACT_METHOD,
            completed=3,
            total=None,
        )
    )
    assert observer.progress is first_progress
    observer.close()
    observer.close()
    assert observer.progress is None and observer.task is None


def test_domain_terminal_shows_grouped_generation_and_active_core_case() -> None:
    observer = DomainTerminalObserver(stream=StringIO(), enabled=True)
    observer.generation_started(32)
    observer.generation_progress(12, 32)
    observer.core_case_started(8, "dise\u00f1o d1; base: c0; a\u00f1adidos: c1, c4")

    assert observer.progress is not None
    tasks = list(observer.progress.tasks)
    assert len(tasks) == 2
    assert tasks[0].completed == 12
    assert tasks[0].total == 32
    assert tasks[0].description == "Combinaciones evaluadas"
    assert "Caso CORE 8" in tasks[1].description
    assert "dise\u00f1o d1; base: c0; a\u00f1adidos: c1, c4" in tasks[1].description
    observer.close()


def test_domain_terminal_uses_indeterminate_large_integer_progress() -> None:
    observer = DomainTerminalObserver(stream=StringIO(), enabled=True)
    enormous = 1 << 20_000
    observer.generation_started(enormous)
    observer.generation_progress(MAX_SAFE_JSON_INTEGER + 1, enormous)

    assert observer.progress is not None
    task = next(iter(observer.progress.tasks))
    assert task.total is None
    assert "2^20000" in task.description
    assert "porcentaje no disponible" in task.description
    observer.close()
