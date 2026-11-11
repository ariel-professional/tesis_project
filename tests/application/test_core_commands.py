from __future__ import annotations

import json
from pathlib import Path

import pytest

from tesis_proyect.application.commands import CoreCommands
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.observation import (
    CommandFinished,
    CommandStarted,
    DiagnosticRaised,
    ExecutionNotification,
)
from tesis_proyect.persistence.workspace import Workspace
from tests.contracts.test_foundation import valid_config

pytestmark = pytest.mark.integration


class RecordingObserver:
    def __init__(self) -> None:
        self.notifications: list[ExecutionNotification] = []

    def notify(self, notification: ExecutionNotification) -> None:
        self.notifications.append(notification)


def _config(*, persist_events: bool = True) -> ExperimentConfig:
    payload = valid_config()
    payload["n"] = 3
    payload["source"] = {"kind": "inline", "edges": [[1, 2]]}
    payload["persistence"] = {
        "policy": "normal",
        "persist_events": persist_events,
    }
    return ExperimentConfig.model_validate(payload)


def test_core_commands_exposes_all_core_operations_as_typed_use_cases(tmp_path: Path) -> None:
    observer = RecordingObserver()
    commands = CoreCommands(Workspace.open(tmp_path), observer=observer)
    config = _config()

    commands.save_experiment("shared-boundary", config)
    assert commands.load_experiment("shared-boundary") == config

    executed = commands.create_run("shared-boundary")
    reference = commands.short_run_reference(executed.run_id)
    assert commands.resolve_run_reference(reference) == executed.run_id
    assert commands.list_runs(experiment_id="shared-boundary").runs[0].manifest == executed

    terminal = commands.run(reference)
    assert terminal.status == "completed"
    assert commands.inspect(reference).run.run_id == executed.run_id  # type: ignore[union-attr]
    exported = commands.export(reference)
    assert exported.report.run_id == executed.run_id
    assert exported.json_report.path.endswith("reports/result.json")
    assert commands.resume(reference).status == "completed"

    cancelled = commands.create_run("shared-boundary")
    response = commands.cancel(cancelled.run_id)
    assert response.status == "accepted"

    command_names = {
        item.command for item in observer.notifications if isinstance(item, CommandStarted)
    }
    assert command_names == {
        "save-experiment",
        "create-run",
        "list-runs",
        "run",
        "inspect",
        "export",
        "resume",
        "cancel",
    }
    assert any(isinstance(item, CommandFinished) for item in observer.notifications)

    events = tmp_path / "runs" / executed.run_id / "logs" / "events.ndjson"
    persisted = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
    assert any(item["event"] == "run_started" for item in persisted)
    assert any(item["event"] == "report_exported" for item in persisted)


def test_core_commands_reports_failures_through_the_same_observer(tmp_path: Path) -> None:
    observer = RecordingObserver()
    commands = CoreCommands(Workspace.open(tmp_path), observer=observer)

    with pytest.raises(OperationalError):
        commands.inspect("ffffffff")

    assert isinstance(observer.notifications[0], CommandStarted)
    assert isinstance(observer.notifications[-2], DiagnosticRaised)
    assert isinstance(observer.notifications[-1], CommandFinished)
    assert observer.notifications[-1].outcome == "error"  # type: ignore[union-attr]
