import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from tesis_proyect.cli import clipboard
from tesis_proyect.cli.app import app
from tests.contracts.test_foundation import valid_config

pytestmark = pytest.mark.integration


def invoke(*arguments: str) -> SimpleNamespace:
    result = CliRunner().invoke(app, list(arguments), catch_exceptions=False)
    return SimpleNamespace(
        returncode=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def invoke_process(
    *arguments: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tesis_proyect", *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        env=env,
    )


def write_config(tmp_path: Path, *, persist_events: bool = False) -> Path:
    data = valid_config()
    data["n"] = 3
    data["source"] = {"kind": "inline", "edges": [[1, 2]]}
    data["persistence"] = {"policy": "normal", "persist_events": persist_events}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def save_and_create(tmp_path: Path, *, persist_events: bool = False) -> str:
    config = write_config(tmp_path, persist_events=persist_events)
    saved = invoke(
        "--workspace",
        str(tmp_path),
        "save-experiment",
        "--id",
        "cli-test",
        "--config",
        str(config),
    )
    assert saved.returncode == 0, saved.stderr
    assert saved.stdout == ""
    created = invoke(
        "--workspace",
        str(tmp_path),
        "create-run",
        "--experiment",
        "cli-test",
    )
    assert created.returncode == 0, created.stderr
    lines = created.stdout.splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "run_created"
    return event["run_id"]


def test_usage_error_uses_sysexits_and_human_stderr(tmp_path: Path) -> None:
    result = invoke_process("inspect", "not-a-run")
    assert result.returncode == 64
    assert result.stdout == ""
    assert "Usage error" in result.stderr


def clean_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("TESIS_PROYECT_WORKSPACE", None)
    return environment


def test_cli_fallback_initializes_empty_current_directory(tmp_path: Path) -> None:
    result = invoke_process("list-runs", cwd=tmp_path, env=clean_environment())
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "experiments").is_dir()
    assert (tmp_path / "runs").is_dir()
    assert not any((tmp_path / "runs").iterdir())


def test_cli_fallback_discovers_one_immediate_workspace(tmp_path: Path) -> None:
    (tmp_path / "f1" / "k1").mkdir(parents=True)
    workspace = tmp_path / "f3"
    (workspace / "experiments").mkdir(parents=True)
    (workspace / "runs").mkdir()
    result = invoke_process("list-runs", cwd=tmp_path, env=clean_environment())
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "tesis_workspace").exists()


def test_cli_fallback_rejects_multiple_workspaces_without_mutation(tmp_path: Path) -> None:
    for name in ("first", "second"):
        (tmp_path / name / "experiments").mkdir(parents=True)
        (tmp_path / name / "runs").mkdir()
    result = invoke_process("list-runs", cwd=tmp_path, env=clean_environment())
    assert result.returncode == 64
    assert "Multiple workspaces were found" in result.stderr
    assert '--workspace "first" COMMAND' in result.stderr
    assert not (tmp_path / "tesis_workspace").exists()


def test_cli_explicit_relative_workspace_precedes_environment_and_fallback(
    tmp_path: Path,
) -> None:
    explicit = tmp_path / "explicit"
    environment_workspace = tmp_path / "environment"
    for path in (explicit, environment_workspace):
        (path / "experiments").mkdir(parents=True)
        (path / "runs").mkdir()
    environment = clean_environment()
    environment["TESIS_PROYECT_WORKSPACE"] = str(environment_workspace)
    result = invoke_process(
        "--workspace",
        "explicit",
        "list-runs",
        cwd=tmp_path,
        env=environment,
    )
    assert result.returncode == 0, result.stderr


def test_invalid_workspace_environment_does_not_fall_back(tmp_path: Path) -> None:
    environment = clean_environment()
    environment["TESIS_PROYECT_WORKSPACE"] = str(tmp_path / "missing")
    result = invoke_process("list-runs", cwd=tmp_path, env=environment)
    assert result.returncode == 64
    assert not (tmp_path / "experiments").exists()


def test_list_runs_defaults_to_human_filters_prefix_and_uses_workspace_env(
    tmp_path: Path,
) -> None:
    run_id = save_and_create(tmp_path)
    arguments = ["--workspace", str(tmp_path), "list-runs", "--prefix", run_id[:1]]
    default = invoke(*arguments)
    explicit = invoke(*arguments, "--format", "human")
    assert default.returncode == explicit.returncode == 0
    assert default.stdout == explicit.stdout
    assert default.stdout.startswith("REF ")
    assert run_id in default.stdout

    ndjson = invoke(
        "--workspace",
        str(tmp_path),
        "list-runs",
        "--experiment",
        "cli-test",
        "--prefix",
        run_id[:8].upper(),
        "--format",
        "ndjson",
    )
    assert [json.loads(line)["run_id"] for line in ndjson.stdout.splitlines()] == [run_id]

    environment = CliRunner().invoke(
        app,
        ["list-runs", "--format", "ndjson"],
        env={"TESIS_PROYECT_WORKSPACE": str(tmp_path)},
        catch_exceptions=False,
    )
    assert environment.exit_code == 0
    assert json.loads(environment.stdout)["run_id"] == run_id
    other_workspace = tmp_path / "other"
    other_workspace.mkdir()
    explicit_override = CliRunner().invoke(
        app,
        ["--workspace", str(tmp_path), "list-runs", "--format", "ndjson"],
        env={"TESIS_PROYECT_WORKSPACE": str(other_workspace)},
        catch_exceptions=False,
    )
    assert json.loads(explicit_override.stdout)["run_id"] == run_id


def test_list_runs_has_no_status_option_and_operation_accepts_unique_prefix(tmp_path: Path) -> None:
    run_id = save_and_create(tmp_path)
    rejected = invoke_process("--workspace", str(tmp_path), "list-runs", "--status", "created")
    assert rejected.returncode == 64
    assert rejected.stdout == ""
    assert "No such option: --status" in rejected.stderr

    inspected = invoke("--workspace", str(tmp_path), "inspect", run_id[:8], "--format", "ndjson")
    assert inspected.returncode == 0
    assert json.loads(inspected.stdout)["run"]["run_id"] == run_id


def test_ambiguous_and_invalid_run_references_are_clear_usage_or_diagnostics(
    tmp_path: Path,
) -> None:
    for run_id in (
        "12345678-1234-4234-8234-123456789abc",
        "12345678-2234-4234-8234-123456789abc",
    ):
        (tmp_path / "runs" / run_id).mkdir(parents=True)
    ambiguous = invoke("--workspace", str(tmp_path), "inspect", "12345678")
    assert ambiguous.returncode == 70
    event = json.loads(ambiguous.stdout)
    assert event["payload"]["error"]["code"] == "ID_COLLISION"
    assert 'list-runs --prefix "12345678"' in ambiguous.stderr

    invalid = invoke_process("--workspace", str(tmp_path), "inspect", "123")
    assert invalid.returncode == 64
    assert invalid.stdout == ""
    assert "at least 8" in invalid.stderr


def test_list_runs_omits_invalid_matching_manifest_with_stderr_warning(tmp_path: Path) -> None:
    run_id = save_and_create(tmp_path)
    corrupt_id = f"{run_id[0]}aaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    (tmp_path / "runs" / corrupt_id).mkdir()
    result = invoke("--workspace", str(tmp_path), "list-runs", "--prefix", run_id[0])
    assert result.returncode == 0
    assert run_id in result.stdout
    assert f"Warning: skipped runs/{corrupt_id}" in result.stderr


def test_create_run_copy_id_is_best_effort_and_preserves_public_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = write_config(tmp_path)
    assert (
        invoke(
            "--workspace",
            str(tmp_path),
            "save-experiment",
            "--id",
            "clipboard-test",
            "--config",
            str(config),
        ).returncode
        == 0
    )

    class RecordingClipboard:
        def __init__(self) -> None:
            self.copied: list[str] = []

        def copy(self, text: str) -> None:
            self.copied.append(text)

    recording = RecordingClipboard()
    monkeypatch.setattr(clipboard, "system_clipboard", recording)
    copied = invoke(
        "--workspace",
        str(tmp_path),
        "create-run",
        "--experiment",
        "clipboard-test",
        "--copy-run-id",
    )
    event = json.loads(copied.stdout)
    assert copied.returncode == 0
    assert recording.copied == [event["run_id"]]
    assert copied.stderr == "Run ID copied to clipboard.\n"

    class BrokenClipboard:
        def copy(self, text: str) -> None:
            del text
            raise RuntimeError("unavailable")

    monkeypatch.setattr(clipboard, "system_clipboard", BrokenClipboard())
    failed_copy = invoke(
        "--workspace",
        str(tmp_path),
        "create-run",
        "--experiment",
        "clipboard-test",
        "--copy-run-id",
    )
    failed_event = json.loads(failed_copy.stdout)
    assert failed_copy.returncode == 0
    assert (tmp_path / "runs" / failed_event["run_id"] / "run.json").is_file()
    assert "was created, but its ID could not be copied" in failed_copy.stderr


def test_full_cli_event_and_inspection_contract(tmp_path: Path) -> None:
    run_id = save_and_create(tmp_path, persist_events=True)
    run = invoke("--workspace", str(tmp_path), "run", run_id[:8])
    assert run.returncode == 0, run.stderr
    assert run.stderr == ""
    events = [json.loads(line) for line in run.stdout.splitlines()]
    names = [event["event"] for event in events]
    assert names[0] == "run_started"
    assert names[-1] == "run_terminal"
    assert names.count("stage_started") == 10
    assert names.count("stage_terminal") == 10
    assert "report_exported" in names
    assert all(event["schema_version"] == "1.0.0" for event in events)

    inspected = invoke("--workspace", str(tmp_path), "inspect", run_id[:8], "--format", "ndjson")
    assert inspected.returncode == 0
    assert len(inspected.stdout.splitlines()) == 1
    run_inspection = json.loads(inspected.stdout)
    assert run_inspection["view"] == "run"
    assert set(run_inspection) == {"schema_version", "view", "run", "pipeline"}

    stage = invoke(
        "--workspace",
        str(tmp_path),
        "inspect",
        run_id,
        "--stage",
        "validate_instance_edges",
        "--format",
        "ndjson",
    )
    assert stage.returncode == 0
    assert len(stage.stdout.splitlines()) == 1
    stage_inspection = json.loads(stage.stdout)
    assert stage_inspection["view"] == "stage"
    assert set(stage_inspection) == {"schema_version", "view", "run_id", "stage", "result"}

    human = invoke("--workspace", str(tmp_path), "inspect", run_id, "--format", "human")
    assert human.returncode == 0
    assert human.stdout.startswith(f"Run {run_id}\nStatus: completed")
    assert "Prescribed edges: [1,2]" in human.stdout
    assert "Case: single_edge" in human.stdout
    assert "Exact: success — value 2" in human.stdout
    assert "Reference: success — value 2" in human.stdout
    assert "Resume: Yes — integrity check and checkpoint repair only." in human.stdout

    persisted = tmp_path / "runs" / run_id / "logs" / "events.ndjson"
    persisted_events = [
        json.loads(line) for line in persisted.read_text(encoding="utf-8").splitlines()
    ]
    assert persisted_events[0]["event"] == "run_created"
    assert persisted_events[-1]["event"] == "run_terminal"


def test_export_only_changes_reports_and_emits_one_event(tmp_path: Path) -> None:
    run_id = save_and_create(tmp_path)
    assert invoke("--workspace", str(tmp_path), "run", run_id).returncode == 0
    pipeline = tmp_path / "runs" / run_id / "pipeline.json"
    stages = tmp_path / "runs" / run_id / "stages"
    before_pipeline = hashlib.sha256(pipeline.read_bytes()).digest()
    before_stages = {
        path.name: hashlib.sha256(path.read_bytes()).digest() for path in stages.glob("*.json")
    }
    exported = invoke("--workspace", str(tmp_path), "export", run_id[:8])
    assert exported.returncode == 0
    lines = exported.stdout.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "report_exported"
    assert hashlib.sha256(pipeline.read_bytes()).digest() == before_pipeline
    assert {
        path.name: hashlib.sha256(path.read_bytes()).digest() for path in stages.glob("*.json")
    } == before_stages


def test_terminal_cancel_is_zero_and_does_not_mutate(tmp_path: Path) -> None:
    run_id = save_and_create(tmp_path)
    assert invoke("--workspace", str(tmp_path), "run", run_id).returncode == 0
    manifest = tmp_path / "runs" / run_id / "run.json"
    before = manifest.read_bytes()
    cancelled = invoke("--workspace", str(tmp_path), "cancel", run_id[:8])
    assert cancelled.returncode == 0
    assert json.loads(cancelled.stdout)["event"] == "run_terminal"
    assert manifest.read_bytes() == before


def test_invalid_configuration_emits_diagnostic_and_english_stderr(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version":"1.0.0"}', encoding="utf-8")
    result = invoke(
        "--workspace",
        str(tmp_path),
        "save-experiment",
        "--id",
        "bad",
        "--config",
        str(path),
    )
    assert result.returncode == 78
    assert json.loads(result.stdout)["event"] == "diagnostic"
    assert result.stderr.strip() == "Configuration is invalid."


def test_cli_failure_resume_cancel_and_not_found_paths(tmp_path: Path) -> None:
    config = write_config(tmp_path)
    payload = json.loads(config.read_text(encoding="utf-8"))
    payload["source"] = {"kind": "inline", "edges": [[1, 1]]}
    config.write_text(json.dumps(payload), encoding="utf-8")
    saved = invoke(
        "--workspace",
        str(tmp_path),
        "save-experiment",
        "--id",
        "invalid-run",
        "--config",
        str(config),
    )
    assert saved.returncode == 0

    first = invoke("--workspace", str(tmp_path), "create-run", "--experiment", "invalid-run")
    failed_id = json.loads(first.stdout)["run_id"]
    failed = invoke("--workspace", str(tmp_path), "run", failed_id)
    assert failed.returncode == 0
    assert json.loads(failed.stdout.splitlines()[-1])["payload"]["status"] == "failed"
    resumed = invoke("--workspace", str(tmp_path), "resume", failed_id[:8])
    assert resumed.returncode == 0
    human_stage = invoke(
        "--workspace",
        str(tmp_path),
        "inspect",
        failed_id,
        "--stage",
        "validate_instance_edges",
        "--format",
        "human",
    )
    assert human_stage.returncode == 0
    assert "Stage: validate_instance_edges" in human_stage.stdout
    assert "Attempts: 2" in human_stage.stdout
    assert "Error: LOOP_EDGE" in human_stage.stdout
    assert "Diagnostics: 1" in human_stage.stdout
    assert invoke("--workspace", str(tmp_path), "export", failed_id).returncode == 0

    second = invoke("--workspace", str(tmp_path), "create-run", "--experiment", "invalid-run")
    cancelled_id = json.loads(second.stdout)["run_id"]
    cancelled = invoke("--workspace", str(tmp_path), "cancel", cancelled_id)
    assert cancelled.returncode == 0
    assert "cancellation_accepted" in {
        json.loads(line)["event"] for line in cancelled.stdout.splitlines()
    }
    terminal = invoke("--workspace", str(tmp_path), "cancel", cancelled_id)
    assert terminal.returncode == 0
    assert json.loads(terminal.stdout)["payload"]["status"] == "cancelled"

    third = invoke("--workspace", str(tmp_path), "create-run", "--experiment", "invalid-run")
    created_id = json.loads(third.stdout)["run_id"]
    rejected_resume = invoke("--workspace", str(tmp_path), "resume", created_id)
    assert rejected_resume.returncode == 65
    assert json.loads(rejected_resume.stdout)["event"] == "diagnostic"

    missing = invoke(
        "--workspace",
        str(tmp_path),
        "inspect",
        "00000000-0000-4000-8000-000000000000",
        "--format",
        "ndjson",
    )
    assert missing.returncode == 66
    absent_experiment = invoke(
        "--workspace", str(tmp_path), "create-run", "--experiment", "does-not-exist"
    )
    assert absent_experiment.returncode == 66
