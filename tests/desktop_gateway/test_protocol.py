from __future__ import annotations

import base64
import io
import json
import os
import queue
import subprocess
import sys
import time
from hashlib import sha256
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from uuid import uuid4

import pytest

from tesis_desktop_gateway.schema_generation import schema_bytes
from tesis_desktop_gateway.server import (
    MAX_MESSAGE_BYTES,
    ActiveOperation,
    GatewayServer,
    OperationEmitter,
)
from tesis_domain_extensions.application import DomainApplication
from tesis_domain_extensions.contracts.common import CoreRunAttempt
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_proyect.application.commands import CoreCommands
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode


def _request(command: str, params: object) -> dict[str, object]:
    return {
        "protocol_version": "1.5",
        "message_type": "request",
        "request_id": str(uuid4()),
        "command": command,
        "params": params,
    }


def _send(server: GatewayServer, request: dict[str, object]) -> None:
    server._handle_frame(json.dumps(request, ensure_ascii=False).encode("utf-8"))


def _messages(output: io.BytesIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.getvalue().splitlines()]


def _one_case_n8_draft() -> dict[str, object]:
    draft = json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    draft["study"]["stations"].extend(
        [
            {"id": "s6", "name": "Estación 6"},
            {"id": "s7", "name": "Estación 7"},
            {"id": "s8", "name": "Estación 8"},
        ]
    )
    draft["study"]["designs"][0]["base_component_ids"] = [
        component["id"] for component in draft["study"]["components"]
    ]
    return draft


def _read_process_lines(process: subprocess.Popen[bytes]) -> queue.Queue[bytes | None]:
    lines: queue.Queue[bytes | None] = queue.Queue()

    def collect() -> None:
        assert process.stdout is not None
        for line in iter(process.stdout.readline, b""):
            lines.put(line)
        lines.put(None)

    Thread(target=collect, daemon=True).start()
    return lines


@pytest.fixture
def gateway(tmp_path: Path) -> tuple[GatewayServer, io.BytesIO]:
    (tmp_path / "experiments").mkdir()
    (tmp_path / "runs").mkdir()
    output = io.BytesIO()
    return GatewayServer(tmp_path, input_stream=io.BytesIO(), output_stream=output), output


def test_generated_gateway_schema_has_no_drift() -> None:
    assert Path("desktop_schemas/1.5.0/gateway-message.schema.json").read_bytes() == schema_bytes()


def test_lifecycle_and_unknown_commands_are_strict(
    gateway: tuple[GatewayServer, io.BytesIO],
) -> None:
    server, output = gateway
    request = _request("hello", {})
    _send(server, request)
    invalid = _request("free.invoke", {"functionName": "anything"})
    _send(server, invalid)

    success, error = _messages(output)
    assert success["request_id"] == request["request_id"]
    assert success["result"] == {
        "protocol_version": "1.5",
        "gateway": "tesis-desktop-gateway",
    }
    assert error["status"] == "error"
    assert error["error"]["code"] == "INVALID_MESSAGE"


def test_command_parameters_are_part_of_the_discriminated_schema(
    gateway: tuple[GatewayServer, io.BytesIO],
) -> None:
    server, output = gateway
    _send(server, _request("domain_run.start", {"projectId": "not-supported"}))

    [error] = _messages(output)
    assert error["status"] == "error"
    assert error["error"]["code"] == "INVALID_MESSAGE"

    _send(server, _request("domain_run.delete", {"domain_run_id": "short"}))
    [delete_error] = _messages(output)[1:]
    assert delete_error["error"]["code"] == "INVALID_MESSAGE"


def test_domain_run_delete_uses_the_application_service(
    gateway: tuple[GatewayServer, io.BytesIO],
) -> None:
    server, output = gateway
    prepared = server.application.prepare(Path("examples/domains/inspection-route/comparison.json"))
    run = server.application.reserve_grouped_run(prepared.domain_experiment_id)

    request = _request("domain_run.delete", {"domain_run_id": run.domain_run_id})
    _send(server, request)

    [response] = _messages(output)
    assert response["request_id"] == request["request_id"]
    assert response["status"] == "success"
    assert response["result"] == {
        "deleted_domain_run_id": run.domain_run_id,
        "deleted_domain_experiment": prepared.domain_experiment_id,
        "preserved_template": False,
    }
    assert not (server.workspace / "domain_runs" / run.domain_run_id).exists()


def test_domain_result_returns_the_confirmed_artifact_without_rendering(
    gateway: tuple[GatewayServer, io.BytesIO], monkeypatch: pytest.MonkeyPatch
) -> None:
    server, output = gateway
    run_id = str(uuid4())
    confirmed = {"domain_run_id": run_id, "confirmed": True}
    monkeypatch.setattr(
        server.application,
        "confirmed_result_document",
        lambda _reference: (confirmed, json.dumps(confirmed).encode("utf-8")),
    )

    def unexpected_render(_reference: str) -> None:
        pytest.fail("the gateway must not rebuild a confirmed result")

    monkeypatch.setattr(server.application, "render", unexpected_render)
    _send(server, _request("domain_run.result", {"domain_run_id": run_id}))

    [response] = _messages(output)
    assert response["status"] == "success"
    assert response["result"] == confirmed


def test_indexed_queries_dispatch_only_typed_run_scoped_arguments(
    gateway: tuple[GatewayServer, io.BytesIO], monkeypatch: pytest.MonkeyPatch
) -> None:
    server, output = gateway
    run_id = str(uuid4())
    calls: list[tuple[str, str, dict[str, object]]] = []
    monkeypatch.setattr(
        server.application,
        "query_fast_result",
        lambda reference, operation, params: (
            calls.append((reference, operation, params)) or {"items": [], "total": 0}
        ),
    )
    _send(
        server,
        _request(
            "domain_run.case_page",
            {
                "domain_run_id": run_id,
                "design_id": "design-a",
                "order": "case",
                "direction": "descending",
                "page": 2,
            },
        ),
    )
    [response] = _messages(output)
    assert response["status"] == "success"
    assert calls == [
        (
            run_id,
            "case_page",
            {
                "design_id": "design-a",
                "order": "case",
                "direction": "descending",
                "page": 2,
            },
        )
    ]


def test_large_domain_result_uses_a_bounded_workspace_reference(
    gateway: tuple[GatewayServer, io.BytesIO], monkeypatch: pytest.MonkeyPatch
) -> None:
    server, output = gateway
    run_id = str(uuid4())
    document = json.dumps({"content": "x" * MAX_MESSAGE_BYTES}).encode("utf-8")
    result_directory = server.workspace / "domain_runs" / run_id
    result_directory.mkdir(parents=True)
    (result_directory / "result.json").write_bytes(document)
    monkeypatch.setattr(
        server.application,
        "confirmed_result_document",
        lambda _reference: ({"content": "x" * MAX_MESSAGE_BYTES}, document),
    )

    _send(server, _request("domain_run.result", {"domain_run_id": run_id}))

    [response] = _messages(output)
    assert len(output.getvalue()) <= MAX_MESSAGE_BYTES
    assert response["status"] == "success"
    assert response["result"] == {
        "$desktop_transport": "domain-result-file-v1",
        "domain_run_id": run_id,
        "size_bytes": len(document),
        "sha256": sha256(document).hexdigest(),
    }

    _send(
        server,
        _request(
            "attachments.read",
            {"sha256": response["result"]["sha256"], "offset": 0, "length": 512},
        ),
    )
    chunk = _messages(output)[-1]
    assert base64.b64decode(chunk["result"]["data"], validate=True) == document[:512]


def test_user_template_is_validated_and_survives_gateway_restart(
    gateway: tuple[GatewayServer, io.BytesIO],
) -> None:
    server, output = gateway
    draft = json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    _send(server, _request("templates.save", {"draft": draft}))
    saved = _messages(output)[-1]
    template_id = saved["result"]["template_id"]

    restarted_output = io.BytesIO()
    restarted = GatewayServer(
        server.workspace,
        input_stream=io.BytesIO(),
        output_stream=restarted_output,
    )
    _send(restarted, _request("templates.list", {}))
    listing = _messages(restarted_output)[-1]["result"]
    saved_descriptor = next(item for item in listing if item["template_id"] == template_id)
    assert saved_descriptor["domain_version"] == "1.0.0"

    _send(restarted, _request("templates.load", {"template_id": template_id}))
    loaded = _messages(restarted_output)[-1]["result"]
    assert loaded["study"]["title"] == draft["study"]["title"]


def test_active_cancel_writes_one_response_when_core_control_is_unavailable(
    gateway: tuple[GatewayServer, io.BytesIO],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, output = gateway
    domain_run_id = str(uuid4())
    server.active = ActiveOperation(
        operation_id=str(uuid4()),
        domain_run_id=domain_run_id,
        cancellation=Event(),
        application=server.application,
        thread=Thread(),
    )
    monkeypatch.setattr(
        server.application,
        "cancel_active_core",
        lambda **_kwargs: (_ for _ in ()).throw(
            OperationalError(ErrorCode.RUN_CONTROL_UNAVAILABLE, "control unavailable")
        ),
    )

    _send(server, _request("domain_run.cancel", {"domain_run_id": domain_run_id}))

    [response] = _messages(output)
    assert response["status"] == "success"
    assert response["result"] == {"status": "accepted"}
    assert server.active.cancellation.is_set()


def test_invalid_utf8_is_rejected_without_stopping_the_gateway(
    gateway: tuple[GatewayServer, io.BytesIO],
) -> None:
    server, output = gateway
    server._handle_frame(b"\xff")
    _send(server, _request("ping", {}))

    error, success = _messages(output)
    assert error["error"]["code"] == "INVALID_MESSAGE"
    assert success["result"] == {"status": "ok"}


def test_oversized_frame_is_discarded_before_next_request(tmp_path: Path) -> None:
    (tmp_path / "experiments").mkdir()
    (tmp_path / "runs").mkdir()
    valid = json.dumps(_request("ping", {})).encode("utf-8") + b"\n"
    input_stream = io.BytesIO(b"x" * (MAX_MESSAGE_BYTES + 10) + b"\n" + valid)
    output = io.BytesIO()
    server = GatewayServer(tmp_path, input_stream=input_stream, output_stream=output)

    server.serve()

    error, success = _messages(output)
    assert error["error"]["code"] == "MESSAGE_TOO_LARGE"
    assert success["result"] == {"status": "ok"}


def test_process_input_reader_buffers_partial_and_multiple_frames(
    gateway: tuple[GatewayServer, io.BytesIO],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, _output = gateway
    frames: list[bytes] = []
    monkeypatch.setattr(server, "_handle_frame", frames.append)
    first = b'{"value":"\xc3\xb1"}'
    second = b'{"value":2}'

    server._consume_process_input(first[:-2])
    server._consume_process_input(first[-2:] + b"\n" + second + b"\n")

    assert frames == [first, second]


def test_process_input_reader_discards_one_oversized_frame_then_recovers(
    gateway: tuple[GatewayServer, io.BytesIO],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, _output = gateway
    errors: list[tuple[str | None, str]] = []
    frames: list[bytes] = []
    monkeypatch.setattr(
        server,
        "_write_protocol_error",
        lambda request_id, code, _message: errors.append((request_id, code)),
    )
    monkeypatch.setattr(server, "_handle_frame", frames.append)

    server._consume_process_input(b"x" * (MAX_MESSAGE_BYTES + 1))
    server._consume_process_input(b"\n" + b'{"command":"ping"}\n')

    assert errors == [(None, "MESSAGE_TOO_LARGE")]
    assert frames == [b'{"command":"ping"}']


def test_failed_grouped_operation_emits_one_error_then_one_failed_terminal(
    gateway: tuple[GatewayServer, io.BytesIO],
) -> None:
    server, output = gateway
    emitter = OperationEmitter(server.writer, str(uuid4()), str(uuid4()))

    class FailingApplication:
        def execute_grouped_run(self, _run_id: str) -> None:
            raise DomainExtensionError("STAGE_TIMEOUT: worker timed out")

    server._run_operation(emitter, FailingApplication(), resume=False)  # type: ignore[arg-type]

    messages = _messages(output)
    assert [message["event"] for message in messages] == ["error", "terminal"]
    assert [message["sequence"] for message in messages] == [1, 2]
    assert messages[0]["data"]["error"]["message"] == "STAGE_TIMEOUT: worker timed out"
    assert messages[1]["data"]["status"] == "failed"


@pytest.mark.parametrize("status", ["cancelled", "failed", "running"])
def test_gateway_resumes_inactive_standard_runs_and_confirms_result(
    gateway: tuple[GatewayServer, io.BytesIO], status: str
) -> None:
    server, output = gateway
    draft = json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    draft["study"]["components"] = draft["study"]["components"][:1]
    draft["study"]["designs"] = [
        {"id": "d", "title": "D", "base_component_ids": [draft["study"]["components"][0]["id"]]}
    ]
    prepared = server.application.prepare_payload(json.dumps(draft).encode())
    manifest = server.application.reserve_grouped_run(prepared.domain_experiment_id)
    server.application.store.write_domain_run(manifest.model_copy(update={"status": status}))
    _send(server, _request("domain_run.resume", {"domain_run_id": manifest.domain_run_id}))
    active = server._active_operation()
    assert active is not None
    active.thread.join(30)
    assert not active.thread.is_alive()
    messages = _messages(output)
    assert messages[0]["status"] == "accepted"
    assert not [m for m in messages if m.get("event") == "error"], messages
    assert messages[-1]["data"]["status"] == "completed"
    confirmed, _ = server.application.store.load_domain_run(manifest.domain_run_id)
    assert confirmed.status == "completed"
    assert server.application.confirmed_result(manifest.domain_run_id)


def test_domain_execution_lock_rejects_other_process_and_gateway_without_mutation(
    gateway: tuple[GatewayServer, io.BytesIO],
) -> None:
    server, output = gateway
    prepared = server.application.prepare_payload(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    manifest = server.application.reserve_grouped_run(prepared.domain_experiment_id)
    server.application.store.write_domain_run(manifest.model_copy(update={"status": "failed"}))
    path = server.workspace / "domain_runs" / manifest.domain_run_id / "domain_run.json"
    before = path.read_bytes()
    script = """
import sys
from pathlib import Path
from tesis_domain_extensions.application import DomainApplication
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_proyect.application.commands import CoreCommands
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode
root = Path(sys.argv[1])
app = DomainApplication(root, CoreCommands.open(root))
try:
    app.resume(sys.argv[2])
except DomainExtensionError as exc:
    assert isinstance(exc.__cause__, OperationalError)
    assert exc.__cause__.code == ErrorCode.RUN_ALREADY_ACTIVE
else:
    raise AssertionError('another process acquired the active run')
finally:
    app.close()
"""
    with server.application.store.domain_execution(manifest.domain_run_id):
        child = subprocess.run(
            [sys.executable, "-c", script, str(server.workspace), manifest.domain_run_id],
            capture_output=True,
            timeout=20,
        )
        assert child.returncode == 0, child.stderr.decode(errors="replace")
        _send(server, _request("domain_run.resume", {"domain_run_id": manifest.domain_run_id}))
        assert _messages(output)[0]["status"] == "error"
        assert server._active_operation() is None
        with pytest.raises(OperationalError) as cancelled:
            server.application.cancel_interrupted_grouped_run(manifest.domain_run_id)
        assert cancelled.value.code == ErrorCode.RUN_ALREADY_ACTIVE
        with pytest.raises(DomainExtensionError, match="activa"):
            server.application.delete_domain_run(manifest.domain_run_id)
        assert path.read_bytes() == before
    with server.application.store.domain_execution(manifest.domain_run_id):
        assert path.read_bytes() == before


def test_aggregation_failure_is_persisted_before_gateway_terminal(
    gateway: tuple[GatewayServer, io.BytesIO], monkeypatch: pytest.MonkeyPatch
) -> None:
    server, output = gateway
    draft = json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    draft["study"]["components"] = draft["study"]["components"][:1]
    draft["study"]["designs"] = [
        {"id": "d", "title": "D", "base_component_ids": [draft["study"]["components"][0]["id"]]}
    ]
    prepared = server.application.prepare_payload(json.dumps(draft).encode())
    manifest = server.application.reserve_grouped_run(prepared.domain_experiment_id)

    def fail(*_args: object, **_kwargs: object) -> None:
        current, _ = server.application.store.load_domain_run(manifest.domain_run_id)
        assert current.status == "running"
        raise ValueError("aggregation failed")

    monkeypatch.setattr(DomainApplication, "_render_grouped_run", fail)
    _send(server, _request("domain_run.resume", {"domain_run_id": manifest.domain_run_id}))
    active = server._active_operation()
    assert active is not None
    active.thread.join(30)
    assert not active.thread.is_alive()
    assert _messages(output)[-1]["data"]["status"] == "failed"
    current, _ = server.application.store.load_domain_run(manifest.domain_run_id)
    assert current.status == "failed"
    assert not (server.workspace / "domain_runs" / manifest.domain_run_id / "result.json").exists()


def test_process_death_releases_domain_execution_for_recovery(
    gateway: tuple[GatewayServer, io.BytesIO],
) -> None:
    server, _output = gateway
    prepared = server.application.prepare_payload(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    manifest = server.application.reserve_grouped_run(prepared.domain_experiment_id)
    script = """
import sys
from pathlib import Path
from tesis_domain_extensions.application import DomainApplication
from tesis_proyect.application.commands import CoreCommands
root = Path(sys.argv[1])
app = DomainApplication(root, CoreCommands.open(root))
with app.store.domain_execution(sys.argv[2]) as (manifest, adapter):
    app._activate_grouped_run(adapter, manifest)
    print('owned', flush=True)
    sys.stdin.readline()
"""
    child = subprocess.Popen(
        [sys.executable, "-u", "-c", script, str(server.workspace), manifest.domain_run_id],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        lines = _read_process_lines(child)
        assert lines.get(timeout=15).strip() == b"owned"
        with pytest.raises(DomainExtensionError) as busy:
            server.application.resume(manifest.domain_run_id)
        assert isinstance(busy.value.__cause__, OperationalError)
        assert busy.value.__cause__.code == ErrorCode.RUN_ALREADY_ACTIVE
    finally:
        child.kill()
        child.communicate(timeout=10)
    resumed = server.application.resume(manifest.domain_run_id)
    assert resumed.manifest.status == "completed"


def test_gateway_startup_preserves_a_live_fast_run(
    gateway: tuple[GatewayServer, io.BytesIO],
) -> None:
    server, _output = gateway
    draft = json.loads(
        Path("examples/domains/single-row-facility-layout/v2-complete.json").read_bytes()
    )
    draft["schema_version"] = draft["domain"]["version"] = "2.1.0"
    draft["execution"]["mode"] = "high_performance"
    prepared = server.application.prepare_payload(json.dumps(draft).encode())
    reserved = server.application.reserve_grouped_run(prepared.domain_experiment_id)
    with server.application.store.domain_execution(reserved.domain_run_id) as (manifest, adapter):
        server.application._activate_grouped_run(adapter, manifest)
        recovered = GatewayServer(
            server.workspace, input_stream=io.BytesIO(), output_stream=io.BytesIO()
        )
        try:
            current, _ = recovered.application.store.load_domain_run(reserved.domain_run_id)
            assert current.status == "running"
        finally:
            recovered.application.close()
            recovered.attachments.close()


@pytest.mark.integration
def test_gateway_process_keeps_control_read_nonblocking_while_core_workers_spawn(
    tmp_path: Path,
) -> None:
    """A real stdin pipe reproduces the former 30 s worker timeouts."""

    (tmp_path / "experiments").mkdir()
    (tmp_path / "runs").mkdir()
    environment = dict(os.environ)
    environment["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        [sys.executable, "-m", "tesis_desktop_gateway.cli", "--workspace", str(tmp_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=Path.cwd(),
        env=environment,
    )
    lines = _read_process_lines(process)

    def send(request: dict[str, object]) -> None:
        assert process.stdin is not None
        process.stdin.write(json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n")
        process.stdin.flush()

    def receive(deadline: float) -> dict[str, object]:
        remaining = deadline - time.monotonic()
        assert remaining > 0, "El gateway no respondió dentro del límite."
        line = lines.get(timeout=remaining)
        assert line is not None, "El gateway terminó antes de responder."
        return json.loads(line)

    started = time.monotonic()
    try:
        prepare = _request("study.prepare", {"draft": _one_case_n8_draft()})
        send(prepare)
        prepared = receive(started + 10)
        assert prepared["status"] == "success"
        experiment_id = prepared["result"]["domain_experiment_id"]

        start = _request("domain_run.start", {"domain_experiment_id": experiment_id})
        send(start)
        messages: list[dict[str, object]] = []
        while time.monotonic() - started < 10:
            message = receive(started + 10)
            messages.append(message)
            if message["message_type"] == "event" and message["event"] == "terminal":
                break
        else:
            pytest.fail("La ejecución no terminalizó dentro de diez segundos.")

        assert messages[0]["message_type"] == "response"
        assert messages[0]["status"] == "accepted"
        events = [message for message in messages if message["message_type"] == "event"]
        assert events[0]["event"] == "generation_started"
        assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
        core_started = [event for event in events if event["event"] == "core_case_started"]
        assert core_started
        assert all(event["data"]["core_run_id"] for event in core_started)
        assert {event["data"]["description"] for event in core_started} == {
            "Diseño base · sin restricciones agregadas"
        }
        assert events[-1]["data"]["status"] == "completed"
        assert time.monotonic() - started < 10

        domain_run_id = messages[0]["result"]["domain_run_id"]
        app = DomainApplication(tmp_path, CoreCommands.open(tmp_path))
        manifest, _adapter = app.store.load_domain_run(domain_run_id)
        core = app.core.inspect_run(manifest.cases[0].attempts[-1].core_run_id)
        stages = {stage.stage.value: stage.status.value for stage in core.pipeline.ordered_stages}
        assert stages["run_exact_method"] == "success"
        assert stages["run_reference_method"] == "success"
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)


def test_recovery_requires_a_new_cancel_or_resume_decision(
    gateway: tuple[GatewayServer, io.BytesIO],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, _output = gateway
    draft = json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    prepared = server.application.prepare_payload(json.dumps(draft).encode())
    manifest = server.application.reserve_grouped_run(prepared.domain_experiment_id)
    loaded = server.application.store.resolve(prepared.domain_experiment_id)
    case = next(
        loaded.adapter.generate_cases(
            loaded.record.domain_config,
            loaded.record.projection_context,
        ).cases
    )
    persisted_case = loaded.adapter.build_persisted_case(case, core_run_id=str(uuid4()))
    persisted_case = persisted_case.model_copy(
        update={
            "attempts": [CoreRunAttempt(core_run_id=persisted_case.core_run_id, status="running")]
        }
    )
    _, adapter = server.application.store.load_domain_run(manifest.domain_run_id)
    interrupted = server.application._update_group_manifest(
        adapter,
        manifest,
        status="running",
        generator_cursor=1,
        cases=[persisted_case],
    )
    server.application.store.write_domain_run(interrupted)

    recovered_output = io.BytesIO()
    recovered = GatewayServer(server.workspace, output_stream=recovered_output)
    persisted, _ = recovered.application.store.load_domain_run(manifest.domain_run_id)
    assert persisted.status == "running"
    assert recovered._active_operation() is None
    monkeypatch.setattr(recovered.application.core, "cancel", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        recovered.application.core,
        "inspect_run",
        lambda _run_id: SimpleNamespace(
            run=SimpleNamespace(status=SimpleNamespace(value="cancelled"))
        ),
    )

    _send(
        recovered,
        _request("domain_run.cancel", {"domain_run_id": manifest.domain_run_id}),
    )

    [response] = _messages(recovered_output)
    terminal, _ = recovered.application.store.load_domain_run(manifest.domain_run_id)
    assert response["result"] == {"status": "accepted"}
    assert terminal.status == "cancelled"
    assert terminal.cases[0].attempts[-1].status == "cancelled"

    completed_case = terminal.cases[0].model_copy(
        update={
            "attempts": [
                CoreRunAttempt(
                    core_run_id=terminal.cases[0].core_run_id,
                    status="completed",
                )
            ]
        }
    )
    recoverable = recovered.application._update_group_manifest(
        adapter,
        terminal,
        status="running",
        cases=[completed_case],
    )
    recovered.application.store.write_domain_run(recoverable)
    recovered_output.seek(0)
    recovered_output.truncate()
    _send(
        recovered,
        _request("domain_run.cancel", {"domain_run_id": manifest.domain_run_id}),
    )
    skipped, _ = recovered.application.store.load_domain_run(manifest.domain_run_id)
    assert skipped.status == "cancelled"
    assert skipped.cases[0].status == "completed"

    completed = recovered.application._update_group_manifest(adapter, skipped, status="completed")
    recovered.application.store.write_domain_run(completed)
    recovered_output.seek(0)
    recovered_output.truncate()
    _send(
        recovered,
        _request("domain_run.cancel", {"domain_run_id": manifest.domain_run_id}),
    )
    [error] = _messages(recovered_output)
    assert error["status"] == "error"


@pytest.mark.integration
def test_start_is_accepted_once_before_sequenced_events(
    gateway: tuple[GatewayServer, io.BytesIO],
) -> None:
    server, output = gateway
    draft = json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    prepare = _request("study.prepare", {"draft": draft})
    _send(server, prepare)
    prepared = _messages(output)[0]
    experiment_id = prepared["result"]["domain_experiment_id"]
    output.seek(0)
    output.truncate()

    start = _request("domain_run.start", {"domain_experiment_id": experiment_id})
    _send(server, start)
    active = server._active_operation()
    assert active is not None
    active.thread.join(timeout=60)
    assert not active.thread.is_alive()

    messages = _messages(output)
    assert messages[0]["message_type"] == "response"
    assert messages[0]["status"] == "accepted"
    assert sum(item["message_type"] == "response" for item in messages) == 1
    events = [item for item in messages if item["message_type"] == "event"]
    assert [item["sequence"] for item in events] == list(range(1, len(events) + 1))
    assert events[0]["event"] == "generation_started"
    assert events[-1]["event"] == "terminal"
    assert events[-1]["data"]["status"] == "completed"
    core_started = [item for item in events if item["event"] == "core_case_started"]
    assert core_started
    assert all(item["data"]["core_run_id"] for item in core_started)


def test_documentary_files_survive_template_prepare_and_gateway_restart(
    gateway: tuple[GatewayServer, io.BytesIO],
) -> None:
    import base64

    server, output = gateway
    content = b"%PDF-1.7\n% technical document\n%%EOF\n"
    _send(
        server,
        _request(
            "attachments.begin",
            {"name": "plano.pdf", "media_type": "application/pdf", "size_bytes": len(content)},
        ),
    )
    upload_id = _messages(output)[-1]["result"]["upload_id"]
    _send(
        server,
        _request(
            "attachments.append",
            {"upload_id": upload_id, "offset": 0, "data": base64.b64encode(content).decode()},
        ),
    )
    _send(server, _request("attachments.finish", {"upload_id": upload_id}))
    attachment = _messages(output)[-1]["result"]
    draft = json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    for entity in [draft["study"], draft["study"]["components"][0], draft["study"]["designs"][0]]:
        entity["description"] = "Motivo documentado"
        entity["attachments"] = [attachment]
    _send(server, _request("templates.save", {"draft": draft}))
    assert _messages(output)[-1]["status"] == "success"
    _send(server, _request("study.prepare", {"draft": draft}))
    prepared = _messages(output)[-1]
    assert prepared["status"] == "success", prepared
    experiment_id = prepared["result"]["domain_experiment_id"]
    assert len(list((server.workspace / "domain_attachments").iterdir())) == 1
    server.attachments.close()

    restarted_output = io.BytesIO()
    restarted = GatewayServer(
        server.workspace, input_stream=io.BytesIO(), output_stream=restarted_output
    )
    _send(
        restarted,
        _request("attachments.read", {"sha256": attachment["sha256"], "offset": 0, "length": 8}),
    )
    assert _messages(restarted_output)[-1]["status"] == "error"
    _send(restarted, _request("study.documentation", {"domain_experiment_id": experiment_id}))
    documented = _messages(restarted_output)[-1]["result"]
    assert documented["study"]["components"][0]["attachments"] == [attachment]
    _send(
        restarted,
        _request(
            "attachments.read",
            {"sha256": attachment["sha256"], "offset": 0, "length": len(content)},
        ),
    )
    assert base64.b64decode(_messages(restarted_output)[-1]["result"]["data"]) == content
    draft["study"]["attachments"] = []
    _send(restarted, _request("templates.save", {"draft": draft}))
    assert _messages(restarted_output)[-1]["status"] == "success"
    assert (server.workspace / "domain_attachments" / attachment["sha256"]).read_bytes() == content
    restarted.attachments.close()
