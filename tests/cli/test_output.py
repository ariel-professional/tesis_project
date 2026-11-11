from __future__ import annotations

from io import StringIO
from uuid import UUID

import pytest
from rich.text import Text

from tesis_proyect.application.experiments import ExperimentService
from tesis_proyect.application.operations import RunOperations
from tesis_proyect.cli.event_adapter import PublicEventObserver
from tesis_proyect.cli.terminal_adapter import TerminalUiObserver, format_human_duration
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import StageId
from tesis_proyect.observation import (
    BestEffortExecutionObserver,
    CommandFinished,
    CommandStarted,
    CompositeExecutionObserver,
    NullExecutionObserver,
    RunStarted,
    StageProgress,
    StageStarted,
)
from tesis_proyect.persistence.workspace import Workspace
from tests.contracts.test_foundation import valid_config


class RecordingObserver:
    def __init__(self) -> None:
        self.items: list[object] = []

    def notify(self, notification: object) -> None:
        self.items.append(notification)


class BrokenObserver:
    def notify(self, notification: object) -> None:
        del notification
        raise RuntimeError("visual failure")


class TerminalBuffer(StringIO):
    def isatty(self) -> bool:
        return True


def test_null_composite_and_best_effort_observers_preserve_delivery() -> None:
    notice = CommandStarted(command="run")
    first = RecordingObserver()
    second = RecordingObserver()
    observer = CompositeExecutionObserver(
        NullExecutionObserver(),
        first,
        BestEffortExecutionObserver(BrokenObserver()),
        second,
    )
    observer.notify(notice)
    assert first.items == second.items == [notice]


def test_public_event_adapter_ignores_progress_and_maps_lifecycle() -> None:
    events = []
    observer = PublicEventObserver(events.append)
    observer.notify(
        StageProgress(
            run_id="12345678-1234-4234-8234-123456789abc",
            stage=StageId.RUN_REFERENCE_METHOD,
            completed=1,
            total=2,
        )
    )
    assert events == []
    observer.notify(
        RunStarted(
            run_id="12345678-1234-4234-8234-123456789abc",
            timestamp="2026-08-06T00:00:00.000Z",
        )
    )
    assert [event.event for event in events] == ["run_started"]


def test_progress_rejects_invalid_counters() -> None:
    with pytest.raises(ValueError):
        StageProgress(
            run_id="run",
            stage=StageId.RUN_REFERENCE_METHOD,
            completed=3,
            total=2,
        )
    with pytest.raises(ValueError):
        StageProgress(
            run_id="run",
            stage=StageId.RUN_REFERENCE_METHOD,
            completed=-1,
            total=None,
        )


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0 segundos"),
        (1, "1 segundo"),
        (59, "59 segundos"),
        (60, "1 minuto"),
        (61, "1 minuto con 1 segundo"),
        (3_599, "59 minutos con 59 segundos"),
        (3_600, "1 hora"),
        (3_601, "1 hora con 1 segundo"),
        (3_661, "1 hora con 1 minuto y 1 segundo"),
        (86_399, "23 horas con 59 minutos y 59 segundos"),
        (86_400, "1 día"),
        (90_061, "1 día con 1 hora"),
        (30 * 86_400, "1 mes"),
        (31 * 86_400, "1 mes con 1 día"),
        (365 * 86_400, "1 año"),
        ((365 + 60) * 86_400, "1 año con 2 meses"),
        (1_350_132 * 365 * 86_400, "1.350.132 años"),
    ],
)
def test_human_duration_adapts_scale_and_precision(seconds: int, expected: str) -> None:
    assert format_human_duration(seconds) == expected


def test_terminal_adapter_is_silent_without_tty(tmp_path) -> None:
    stream = StringIO()
    observer = TerminalUiObserver(Workspace.open(tmp_path), stream=stream)
    observer.notify(CommandStarted(command="save-experiment"))
    observer.close()
    assert stream.getvalue() == ""


def test_terminal_adapter_renders_stage_progress_and_next_command(tmp_path) -> None:
    stream = TerminalBuffer()
    observer = TerminalUiObserver(Workspace.open(tmp_path), stream=stream)
    observer.notify(CommandStarted(command="save-experiment"))
    observer.notify(
        StageStarted(
            run_id="12345678-1234-4234-8234-123456789abc",
            timestamp="2026-08-06T00:00:00.000Z",
            stage=StageId.RUN_REFERENCE_METHOD,
            ordinal=7,
            total_stages=10,
            attempt=1,
        )
    )
    observer.notify(
        StageProgress(
            run_id="12345678-1234-4234-8234-123456789abc",
            stage=StageId.RUN_REFERENCE_METHOD,
            completed=1,
            total=2,
        )
    )
    observer.close()
    observer.notify(
        CommandFinished(command="save-experiment", outcome="success", experiment_id="demo")
    )
    output = Text.from_ansi(stream.getvalue()).plain
    assert "Stage 7/10" in output
    assert "Run reference method" in output
    assert "Transcurrido:" in output
    assert "Restante estimado:" in output
    assert "Next command:" in output
    assert "create-run --experiment demo" in output


def test_terminal_adapter_shows_full_and_short_run_references(tmp_path) -> None:
    workspace = Workspace.open(tmp_path)
    stream = TerminalBuffer()
    terminal = TerminalUiObserver(workspace, stream=stream)
    service = ExperimentService(
        workspace,
        uuid_factory=lambda: UUID("435b552c-231f-48ab-9223-4579538b1f55"),
        clock=lambda: "2026-08-11T04:15:00.000Z",
    )
    service.save_experiment("demo", ExperimentConfig.model_validate(valid_config()))
    manifest = service.create_run("demo")
    terminal.notify(
        CommandFinished(
            command="create-run",
            outcome="success",
            run_id=manifest.run_id,
            experiment_id="demo",
            run_status=manifest.status,
        )
    )
    output = Text.from_ansi(stream.getvalue()).plain
    assert f"Result: Run {manifest.run_id} created." in output
    assert "Short reference: 435b552c" in output
    assert "run 435b552c" in output


@pytest.mark.parametrize(
    ("experiment_id", "edges", "expected_status", "expected_text"),
    [
        ("guided-valid", [[1, 2]], "completed", "Reference method counted 2"),
        ("guided-invalid", [[1, 1]], "failed", "LOOP_EDGE"),
    ],
)
def test_terminal_adapter_renders_complete_pipeline_paths(
    tmp_path,
    experiment_id: str,
    edges: list[list[int]],
    expected_status: str,
    expected_text: str,
) -> None:
    workspace = Workspace.open(tmp_path)
    stream = TerminalBuffer()
    terminal = TerminalUiObserver(workspace, stream=stream)
    data = valid_config()
    data["n"] = 3
    data["source"] = {"kind": "inline", "edges": edges}
    service = ExperimentService(workspace, observer=terminal)
    service.save_experiment(experiment_id, ExperimentConfig.model_validate(data))
    manifest = service.create_run(experiment_id)
    terminal.notify(CommandStarted(command="run"))
    finished = RunOperations(workspace, observer=terminal).run(manifest.run_id)
    terminal.notify(
        CommandFinished(
            command="run",
            outcome="success",
            run_id=manifest.run_id,
            run_status=finished.status,
        )
    )
    terminal.close()
    output = Text.from_ansi(stream.getvalue()).plain
    assert finished.status == expected_status
    assert "Stage 1/10" in output
    assert "Stage 10/10 finished" in output
    assert expected_text in output
    assert "Next command:" in output
