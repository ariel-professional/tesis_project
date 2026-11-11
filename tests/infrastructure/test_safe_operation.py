from __future__ import annotations

import hashlib
import multiprocessing
import os
from pathlib import Path
from uuid import UUID

import pytest

import tesis_proyect.application.operations as operations_module
from tesis_proyect.application.experiments import ExperimentService
from tesis_proyect.application.operations import RunOperations
from tesis_proyect.cli.event_adapter import PublicEventObserver
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import Cancellation
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import ErrorCode, RunStatus, StageStatus
from tesis_proyect.models.execution import PipelineState, RunManifest
from tesis_proyect.models.protocols import ControlRequest, ControlResponse
from tesis_proyect.models.stages import StageResult
from tesis_proyect.persistence.json_store import JsonStore
from tesis_proyect.persistence.run_repository import RunRepository
from tesis_proyect.persistence.workspace import Workspace
from tesis_proyect.pipeline.orchestrator import PipelineCoordinator
from tesis_proyect.runner.control_endpoint import (
    _unix_runtime_root,
    canonical_workspace_bytes,
    control_digest,
    control_endpoint,
)
from tesis_proyect.runner.control_protocol import decode_control, encode_control
from tesis_proyect.runner.control_transport import (
    ControlServer,
    send_control,
)
from tesis_proyect.runner.control_windows import (
    _verify_windows_pipe_dacl,
    _windows_security_attributes,
)
from tesis_proyect.runner.locking import RunExecutionLock, WorkspaceWriteLock, is_run_active
from tests.contracts.test_foundation import valid_config

pytestmark = [pytest.mark.integration, pytest.mark.platform]

RUN_UUID = UUID("12345678-1234-4234-8234-123456789abc")
REQUEST_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
NOW = "2026-08-05T15:30:00.000Z"


def _hold_lock(
    path: str, ready: multiprocessing.synchronize.Event, release: multiprocessing.synchronize.Event
) -> None:
    with RunExecutionLock(Path(path)):
        ready.set()
        release.wait(10)


def _hold_workspace_write_lock(
    path: str, ready: multiprocessing.synchronize.Event, release: multiprocessing.synchronize.Event
) -> None:
    with WorkspaceWriteLock(Path(path)):
        ready.set()
        release.wait(10)


def create_run(tmp_path: Path, edges: list[object] | None = None) -> tuple[Workspace, str]:
    data = valid_config()
    data["source"] = {"kind": "inline", "edges": [] if edges is None else edges}
    workspace = Workspace.open(tmp_path)
    service = ExperimentService(workspace, uuid_factory=lambda: RUN_UUID, clock=lambda: NOW)
    service.save_experiment("safe", ExperimentConfig.model_validate(data))
    return workspace, service.create_run("safe").run_id


def request(run_id: str) -> ControlRequest:
    return ControlRequest(
        schema_version="1.0.0",
        request_id=REQUEST_ID,
        command="cancel",
        run_id=run_id,
        requested_at=NOW,
        origin="cli",
        reason=None,
    )


def test_native_lock_distinguishes_presence_from_activity(tmp_path: Path) -> None:
    path = tmp_path / "execution.lock"
    path.touch()
    assert not is_run_active(path)


def test_workspace_write_lock_coordinates_across_processes(tmp_path: Path) -> None:
    path = tmp_path / ".domain-write.lock"
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    process = context.Process(
        target=_hold_workspace_write_lock,
        args=(str(path), ready, release),
    )
    process.start()
    assert ready.wait(10)
    try:
        with pytest.raises(OperationalError) as failure:
            WorkspaceWriteLock(path).acquire()
        assert failure.value.code == ErrorCode.RUN_ALREADY_ACTIVE
    finally:
        release.set()
        process.join(10)
    assert process.exitcode == 0
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    process = context.Process(target=_hold_lock, args=(str(path), ready, release))
    process.start()
    assert ready.wait(10)
    try:
        assert is_run_active(path)
        with pytest.raises(OperationalError) as failure:
            RunExecutionLock(path).acquire()
        assert failure.value.code == ErrorCode.RUN_ALREADY_ACTIVE
    finally:
        release.set()
        process.join(10)
    assert process.exitcode == 0
    assert not is_run_active(path)


def test_endpoint_digest_uses_exact_contract_bytes(tmp_path: Path) -> None:
    run_id = str(RUN_UUID)
    expected = hashlib.sha256(
        b"tesis-proyect-control-v1\0"
        + canonical_workspace_bytes(tmp_path)
        + b"\0"
        + run_id.encode("ascii")
    ).hexdigest()
    assert control_digest(tmp_path, run_id) == expected
    endpoint = control_endpoint(tmp_path, run_id)
    assert expected in endpoint
    assert str(tmp_path) not in endpoint


def test_unix_runtime_selection_handles_secure_missing_and_fallback_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secure = tmp_path / "secure"
    secure.mkdir(mode=0o700)
    os.chmod(secure, 0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(secure))
    selected = _unix_runtime_root()
    assert selected.name in {"tesis-proyect", "tesis-proyect-0"}
    assert selected.is_dir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "missing"))
    assert _unix_runtime_root().is_dir()


def test_control_framing_rejects_oversize_multiline_and_invalid_json() -> None:
    message = request(str(RUN_UUID))
    encoded = encode_control(message, 16384)
    assert decode_control(encoded, ControlRequest, 16384) == message
    with pytest.raises(OperationalError):
        encode_control(message, 10)
    for payload in (b"{}", b"{}\n{}\n", b"not-json\n"):
        with pytest.raises(OperationalError):
            decode_control(payload, ControlRequest, 16384)


def test_local_control_round_trip_and_same_request_identity(tmp_path: Path) -> None:
    cancellation = Cancellation(requested_at=NOW, origin="cli", reason=None)

    def handler(message: ControlRequest) -> ControlResponse:
        return ControlResponse(
            schema_version="1.0.0",
            request_id=message.request_id,
            run_id=message.run_id,
            status="accepted",
            cancellation=cancellation,
            error=None,
        )

    server = ControlServer(tmp_path, str(RUN_UUID), handler, max_bytes=16384)
    server.start()
    try:
        response = send_control(
            tmp_path,
            request(str(RUN_UUID)),
            connect_timeout_ms=5000,
            response_timeout_ms=5000,
            max_bytes=16384,
        )
        assert response.status == "accepted"
        assert response.request_id == REQUEST_ID
    finally:
        server.close()


def test_cancel_created_is_durable_idempotent_and_creates_no_reports(tmp_path: Path) -> None:
    workspace, run_id = create_run(tmp_path)
    events = []
    operations = RunOperations(workspace, observer=PublicEventObserver(events.append))
    first = operations.cancel(request(run_id))
    assert first.status == "accepted"
    manifest = JsonStore(workspace).read_model(
        f"runs/{run_id}/run.json", RunManifest, max_bytes=1_000_000
    )
    assert manifest.status == RunStatus.CANCELLED
    assert manifest.cancellation is not None
    pipeline = JsonStore(workspace).read_model(
        f"runs/{run_id}/pipeline.json", PipelineState, max_bytes=1_000_000
    )
    assert all(item.status == StageStatus.SKIPPED for item in pipeline.ordered_stages)
    assert all(
        result.attempt_count == 1 and result.result is not None
        for result in pipeline.ordered_stages
    )
    assert not any(event.event == "stage_started" for event in events)
    assert sum(event.event == "stage_terminal" for event in events) == 10
    assert not (tmp_path / "runs" / run_id / "reports" / "result.json").exists()
    before = (tmp_path / "runs" / run_id / "run.json").read_bytes()
    second = operations.cancel(request(run_id))
    assert second.status == "terminal"
    assert (tmp_path / "runs" / run_id / "run.json").read_bytes() == before


def test_resume_failed_preserves_attempt_history(tmp_path: Path) -> None:
    workspace, run_id = create_run(tmp_path, [[1, 1]])
    operations = RunOperations(workspace)
    assert operations.run(run_id).status == RunStatus.FAILED
    assert operations.resume(run_id).status == RunStatus.FAILED
    stage = JsonStore(workspace).read_model(
        f"runs/{run_id}/stages/03_validate_instance_edges.json",
        StageResult,
        max_bytes=1_000_000,
    )
    assert [attempt.number for attempt in stage.attempts] == [1, 2]


def test_resume_rejects_created_and_cancelled_runs_but_accepts_integral_completed(
    tmp_path: Path,
) -> None:
    workspace, run_id = create_run(tmp_path)
    operations = RunOperations(workspace)
    with pytest.raises(OperationalError):
        operations.resume(run_id)
    assert operations.run(run_id).status == RunStatus.COMPLETED
    assert operations.resume(run_id).status == RunStatus.COMPLETED

    other_root = tmp_path / "other"
    other_root.mkdir()
    cancelled_workspace, cancelled_id = create_run(other_root)
    cancelled = RunOperations(cancelled_workspace)
    cancelled.cancel(request(cancelled_id))
    with pytest.raises(OperationalError):
        cancelled.resume(cancelled_id)


def test_cancel_abandoned_running_emits_interruption_before_terminalization(
    tmp_path: Path,
) -> None:
    workspace, run_id = create_run(tmp_path)
    repository = RunRepository(workspace, run_id)
    manifest = repository.load_manifest().model_copy(update={"status": RunStatus.RUNNING})
    repository.write_manifest(manifest)
    pipeline = repository.load_pipeline()
    first = pipeline.ordered_stages[0]
    pipeline.ordered_stages[0] = first.model_copy(update={"status": StageStatus.RUNNING})
    repository.write_pipeline(pipeline)
    events = []

    response = RunOperations(workspace, observer=PublicEventObserver(events.append)).cancel(
        request(run_id)
    )
    assert response.status == "accepted"
    names = [event.event for event in events]
    assert names[0] == "run_interruption_detected"
    assert "cancellation_accepted" in names
    assert names[-1] == "run_terminal"
    assert repository.load_manifest().status == RunStatus.CANCELLED


def test_cancel_reloads_terminal_manifest_after_acquiring_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, run_id = create_run(tmp_path)
    repository = RunRepository(workspace, run_id)

    class RacingLock:
        def __init__(self, path: Path) -> None:
            self.path = path

        def acquire(self) -> None:
            current = repository.load_manifest()
            repository.write_manifest(current.model_copy(update={"status": RunStatus.COMPLETED}))

        def release(self) -> None:
            return

    monkeypatch.setattr(operations_module, "RunExecutionLock", RacingLock)
    response = RunOperations(workspace).cancel(request(run_id))
    assert response.status == "terminal"
    assert repository.load_manifest().cancellation is None


def test_control_handler_rejects_wrong_run_and_is_idempotent(tmp_path: Path) -> None:
    workspace, run_id = create_run(tmp_path)
    events = []
    operations = RunOperations(workspace, observer=PublicEventObserver(events.append))
    runner = PipelineCoordinator(workspace, run_id)
    server = operations.control_server(runner)
    wrong = request("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    rejected = server.handler(wrong)
    assert rejected.status == "rejected"
    assert rejected.error is not None
    accepted = server.handler(request(run_id))
    repeated = server.handler(request(run_id))
    assert accepted.status == "accepted"
    assert repeated.status == "already_registered"
    assert [event.event for event in events] == ["cancellation_accepted"]


def test_cancel_delegates_to_active_runner_and_reconciles_terminal_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, run_id = create_run(tmp_path)
    cancellation = Cancellation(requested_at=NOW, origin="cli", reason=None)

    class ActiveLock:
        def __init__(self, path: Path) -> None:
            self.path = path

        def acquire(self) -> None:
            raise OperationalError(ErrorCode.RUN_ALREADY_ACTIVE, "active")

    monkeypatch.setattr(operations_module, "RunExecutionLock", ActiveLock)
    delegated = ControlResponse(
        schema_version="1.0.0",
        request_id=REQUEST_ID,
        run_id=run_id,
        status="accepted",
        cancellation=cancellation,
        error=None,
    )
    monkeypatch.setattr(operations_module, "send_control", lambda *args, **kwargs: delegated)
    assert RunOperations(workspace).cancel(request(run_id)) == delegated

    created = RunRepository(workspace, run_id).load_manifest()
    completed = created.model_copy(update={"status": RunStatus.COMPLETED})
    manifests = iter((created, completed))
    monkeypatch.setattr(RunRepository, "load_manifest", lambda ignored: next(manifests))

    def unavailable(*args: object, **kwargs: object) -> ControlResponse:
        raise OperationalError(ErrorCode.RUN_CONTROL_UNAVAILABLE, "unavailable")

    monkeypatch.setattr(operations_module, "send_control", unavailable)
    reconciled = RunOperations(workspace).cancel(request(run_id))
    assert reconciled.status == "terminal"


def test_cancel_propagates_non_activity_lock_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, run_id = create_run(tmp_path)

    class BrokenLock:
        def __init__(self, path: Path) -> None:
            self.path = path

        def acquire(self) -> None:
            raise OperationalError(ErrorCode.RUN_LOCK_UNAVAILABLE, "broken")

    monkeypatch.setattr(operations_module, "RunExecutionLock", BrokenLock)
    with pytest.raises(OperationalError) as failure:
        RunOperations(workspace).cancel(request(run_id))
    assert failure.value.code == ErrorCode.RUN_LOCK_UNAVAILABLE


@pytest.mark.skipif(os.name != "nt", reason="Windows DACL verification is native-only")
def test_windows_control_endpoint_is_named_pipe(tmp_path: Path) -> None:
    assert control_endpoint(tmp_path, str(RUN_UUID)).startswith(r"\\.\pipe\tesis-proyect-ctl-")


@pytest.mark.skipif(os.name != "nt", reason="Windows DACL verification is native-only")
def test_windows_pipe_security_descriptor_is_exact(tmp_path: Path) -> None:
    import win32file
    import win32pipe

    endpoint = control_endpoint(tmp_path, "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    handle = win32pipe.CreateNamedPipe(
        endpoint,
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
        1,
        16384,
        16384,
        0,
        _windows_security_attributes(),
    )
    try:
        _verify_windows_pipe_dacl(handle)
    finally:
        win32file.CloseHandle(handle)
