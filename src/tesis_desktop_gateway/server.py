from __future__ import annotations

import base64
import json
import os
import sys
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, BinaryIO, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, TypeAdapter, ValidationError

from tesis_desktop_gateway.models import (
    AttachmentAppendParams,
    AttachmentBeginParams,
    AttachmentReadParams,
    AttachmentTransferParams,
    CancelParams,
    CoreCaseStartedEvent,
    CoreProgressEvent,
    DomainRunParams,
    DraftParams,
    ExperimentParams,
    GatewayError,
    GatewayMessage,
    GatewayRequest,
    GatewayResponse,
    GenerationProgressEvent,
    GenerationStartedEvent,
    OperationErrorEvent,
    RunListParams,
    TemplateParams,
    TemplateRunParams,
    TerminalEvent,
)
from tesis_desktop_gateway.observers import GatewayCoreObserver, GatewayGroupedObserver
from tesis_domain_extensions.application import DomainApplication, InterpretedRun
from tesis_domain_extensions.attachment_store import AttachmentStore
from tesis_domain_extensions.catalog import SUPPORTED_DOMAINS
from tesis_domain_extensions.contracts.projection import domain_experiment_id
from tesis_domain_extensions.errors import DomainExtensionError, DomainRunCancelled
from tesis_domain_extensions.projection_store import pretty_json
from tesis_proyect.application.commands import CoreCommands
from tesis_proyect.errors import OperationalError
from tesis_proyect.runner.locking import WorkspaceWriteLock

MAX_MESSAGE_BYTES = 32 * 1024 * 1024
_INPUT_CHUNK_BYTES = 64 * 1024
_INPUT_IDLE_SECONDS = 0.01
_MESSAGE_ADAPTER: TypeAdapter[GatewayMessage] = TypeAdapter(GatewayMessage)
_REQUEST_ADAPTER: TypeAdapter[GatewayRequest] = TypeAdapter(GatewayRequest)
_EVENT_MODELS = {
    "generation_started": GenerationStartedEvent,
    "generation_progress": GenerationProgressEvent,
    "core_case_started": CoreCaseStartedEvent,
    "core_progress": CoreProgressEvent,
    "terminal": TerminalEvent,
    "error": OperationErrorEvent,
}


def _json_value(value: object) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


class MessageWriter:
    def __init__(self, output: BinaryIO) -> None:
        self.output = output
        self.lock = Lock()

    def write(self, message: object) -> None:
        validated = _MESSAGE_ADAPTER.validate_python(message)
        payload = _MESSAGE_ADAPTER.dump_json(validated, exclude_none=False) + b"\n"
        with self.lock:
            self.output.write(payload)
            self.output.flush()


class OperationEmitter:
    def __init__(self, writer: MessageWriter, operation_id: str, domain_run_id: str) -> None:
        self.writer = writer
        self.operation_id = operation_id
        self.domain_run_id = domain_run_id
        self.sequence = 0
        self.lock = Lock()

    def emit(self, event: str, data: dict[str, object]) -> None:
        with self.lock:
            self.sequence += 1
            sequence = self.sequence
        model = _EVENT_MODELS[event]
        self.writer.write(
            model(
                operation_id=self.operation_id,
                sequence=sequence,
                event=event,
                data=data,
            )
        )


@dataclass
class ActiveOperation:
    operation_id: str
    domain_run_id: str
    cancellation: Event
    application: DomainApplication
    thread: Thread


class GatewayServer:
    def __init__(
        self,
        workspace: Path,
        *,
        input_stream: BinaryIO | None = None,
        output_stream: BinaryIO | None = None,
        template_root: Path | None = None,
    ) -> None:
        self.workspace = workspace.resolve(strict=True)
        self._uses_process_stdin = input_stream is None
        self.input = input_stream or sys.stdin.buffer
        self.writer = MessageWriter(output_stream or sys.stdout.buffer)
        self.template_root = template_root or Path(__file__).resolve().parents[2] / "examples"
        self.core = CoreCommands.open(self.workspace)
        self.application = DomainApplication(
            self.workspace,
            self.core,
            template_roots=(self.template_root / "domains",),
        )
        self.application.fail_interrupted_high_performance_runs()
        self.attachments = AttachmentStore(self.workspace)
        self._large_result_documents: dict[str, tuple[str, int]] = {}
        self.stop_requested = False
        self._input_wait = Event()
        self._frame_buffer = bytearray()
        self._discarding_oversized_frame = False
        self.active_lock = Lock()
        self.active: ActiveOperation | None = None

    def serve(self) -> None:
        try:
            if self._uses_process_stdin:
                self._serve_process_stdin()
            else:
                self._serve_injected_stream()
        finally:
            self.application.close()
            self.attachments.close()

    def _serve_injected_stream(self) -> None:
        while not self.stop_requested:
            frame = self.input.readline(MAX_MESSAGE_BYTES + 2)
            if frame == b"":
                break
            if len(frame) > MAX_MESSAGE_BYTES + 1 or not frame.endswith(b"\n"):
                self._write_protocol_error(None, "MESSAGE_TOO_LARGE", "Invalid NDJSON frame.")
                if not frame.endswith(b"\n"):
                    self._discard_frame_remainder()
                continue
            self._handle_frame(frame[:-1])

    def _serve_process_stdin(self) -> None:
        """Read NDJSON without holding a blocking stdin read during CORE spawns."""

        try:
            descriptor = self.input.fileno()
            was_blocking = os.get_blocking(descriptor)
        except (AttributeError, OSError):
            self._serve_injected_stream()
            return
        try:
            os.set_blocking(descriptor, False)
            while not self.stop_requested:
                try:
                    chunk = os.read(descriptor, _INPUT_CHUNK_BYTES)
                except BlockingIOError:
                    self._input_wait.wait(_INPUT_IDLE_SECONDS)
                    continue
                if chunk == b"":
                    return
                self._consume_process_input(chunk)
        finally:
            with suppress(OSError):
                os.set_blocking(descriptor, was_blocking)

    def _consume_process_input(self, chunk: bytes) -> None:
        """Consume complete LF-delimited frames while retaining incomplete bytes."""

        self._frame_buffer.extend(chunk)
        while self._frame_buffer:
            if self._discarding_oversized_frame:
                newline = self._frame_buffer.find(b"\n")
                if newline < 0:
                    self._frame_buffer.clear()
                    return
                del self._frame_buffer[: newline + 1]
                self._discarding_oversized_frame = False
                continue
            newline = self._frame_buffer.find(b"\n")
            if newline < 0:
                if len(self._frame_buffer) > MAX_MESSAGE_BYTES:
                    self._frame_buffer.clear()
                    self._discarding_oversized_frame = True
                    self._write_protocol_error(None, "MESSAGE_TOO_LARGE", "Invalid NDJSON frame.")
                return
            frame = bytes(self._frame_buffer[:newline])
            del self._frame_buffer[: newline + 1]
            if len(frame) > MAX_MESSAGE_BYTES:
                self._write_protocol_error(None, "MESSAGE_TOO_LARGE", "Invalid NDJSON frame.")
                continue
            self._handle_frame(frame)

    def _discard_frame_remainder(self) -> None:
        while True:
            remainder = self.input.readline(MAX_MESSAGE_BYTES + 2)
            if remainder == b"" or remainder.endswith(b"\n"):
                return

    def _handle_frame(self, frame: bytes) -> None:
        request_id: str | None = None
        try:
            document = json.loads(frame.decode("utf-8", errors="strict"))
            if isinstance(document, dict) and isinstance(document.get("request_id"), str):
                request_id = document["request_id"]
            request = _REQUEST_ADAPTER.validate_python(document)
            params = request.params
            if request.command == "domain_run.cancel":
                self._cancel(request, cast(CancelParams, params))
                return
            if request.command == "domain_run.metrics":
                Thread(
                    target=self._dispatch_metrics_request,
                    args=(request, params),
                    name=f"domain-metrics-{request.request_id}",
                    daemon=True,
                ).start()
                return
            response = self._dispatch(request, params)
            if response is not None:
                self.writer.write(response)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            self._write_protocol_error(request_id, "INVALID_MESSAGE", str(exc))
        except (DomainExtensionError, OperationalError, OSError, ValueError) as exc:
            self.writer.write(self._error_response(request_id, exc))

    def _dispatch_metrics_request(self, request: GatewayRequest, params: BaseModel) -> None:
        try:
            response = self._dispatch(request, params)
            if response is not None:
                self.writer.write(response)
        except (DomainExtensionError, OperationalError, OSError, ValueError) as exc:
            self.writer.write(self._error_response(request.request_id, exc))

    def _dispatch(self, request: GatewayRequest, params: BaseModel) -> GatewayResponse | None:
        if request.command in {
            "study.prepare",
            "templates.save",
            "templates.set_for_run",
            "domain_run.start",
            "domain_run.resume",
            "domain_run.delete",
        }:
            with WorkspaceWriteLock(self.workspace / ".domain-write.lock"):
                return self._dispatch_unlocked(request, params)
        return self._dispatch_unlocked(request, params)

    def _dispatch_unlocked(
        self, request: GatewayRequest, params: BaseModel
    ) -> GatewayResponse | None:
        command = request.command
        if command.startswith("attachments."):
            return self._dispatch_attachments(request, params)
        if command == "study.documentation":
            loaded = self.application.store.load(
                cast(ExperimentParams, params).domain_experiment_id
            )
            config = loaded.record.domain_config
            self.attachments.authorize(config)
            return self._success(request.request_id, config)
        if command in {"hello", "ping", "shutdown", "domains.list", "layout.decision_criteria"}:
            return self._dispatch_lifecycle(request, command)
        if command in {
            "templates.list",
            "templates.load",
            "templates.save",
            "templates.set_for_run",
        }:
            return self._dispatch_templates(request, command, params)
        if command in {
            "study.validate",
            "study.prepare",
            "layout.validate_forest",
            "layout.estimate_combinations",
        }:
            return self._dispatch_study(request, command, cast(DraftParams, params))
        return self._dispatch_run(request, command, params)

    def _dispatch_attachments(self, request: GatewayRequest, params: BaseModel) -> GatewayResponse:
        command = request.command
        result: object
        if command == "attachments.begin":
            begin = cast(AttachmentBeginParams, params)
            result = {
                "upload_id": self.attachments.begin(begin.name, begin.media_type, begin.size_bytes)
            }
        elif command == "attachments.append":
            block = cast(AttachmentAppendParams, params)
            result = {
                "received": self.attachments.append(block.upload_id, block.offset, block.data)
            }
        elif command == "attachments.read":
            read = cast(AttachmentReadParams, params)
            transported = self._read_large_result(read.sha256, read.offset, read.length)
            result = {
                "data": transported
                if transported is not None
                else self.attachments.read(read.sha256, read.offset, read.length)
            }
        elif command == "attachments.finish":
            result = self.attachments.finish(cast(AttachmentTransferParams, params).upload_id)
        else:
            self.attachments.abort(cast(AttachmentTransferParams, params).upload_id)
            result = {"aborted": True}
        return self._success(request.request_id, result)

    def _dispatch_lifecycle(self, request: GatewayRequest, command: str) -> GatewayResponse:
        if command == "hello":
            result: object = {
                "protocol_version": "1.5",
                "gateway": "tesis-desktop-gateway",
            }
        elif command == "ping":
            result = {"status": "ok"}
        elif command == "shutdown":
            if self._active_operation() is not None:
                raise DomainExtensionError("No se puede cerrar el gateway durante una operación.")
            self.stop_requested = True
            result = {"status": "shutting_down"}
        elif command == "layout.decision_criteria":
            adapter = SUPPORTED_DOMAINS[("single-row-facility-layout", "2.0.0")]
            result = [item.model_dump(mode="json") for item in adapter.decision_criteria()]
        else:
            result = [
                {
                    "domain_id": domain_id,
                    "domain_version": version,
                    "description": adapter.description,
                }
                for (domain_id, version), adapter in sorted(SUPPORTED_DOMAINS.items())
            ]
        return self._success(request.request_id, result)

    def _dispatch_templates(
        self, request: GatewayRequest, command: str, params: BaseModel
    ) -> GatewayResponse:
        result: object
        if command == "templates.list":
            result = self._template_listing()
        elif command == "templates.load":
            result = self._load_template(cast(TemplateParams, params).template_id)
        elif command == "templates.save":
            result = self._save_template(cast(DraftParams, params).draft)
        else:
            run_params = cast(TemplateRunParams, params)
            result = self._set_template_for_run(run_params.domain_run_id, run_params.enabled)
        return self._success(request.request_id, result)

    def _dispatch_study(
        self, request: GatewayRequest, command: str, params: DraftParams
    ) -> GatewayResponse:
        payload = self._draft_bytes(params.draft)
        result: object
        if command in {"study.validate", "layout.validate_forest"}:
            config = self.application.validate_payload(payload)
            if command == "layout.validate_forest":
                typed_config = cast(Any, config)
                adapter = SUPPORTED_DOMAINS[(typed_config.domain.id, typed_config.domain.version)]
                adapter.project(config)
            self.attachments.authorize(config)
            result = {"valid": True, "draft": config}
        elif command == "layout.estimate_combinations":
            total = self.application.estimate_payload(payload)
            result = {"theoretical_combinations": total}
        else:
            config = self.application.validate_payload(payload)
            self.attachments.publish(config)
            result = self.application.prepare_payload(payload)
        return self._success(request.request_id, result)

    def _dispatch_run(  # noqa: C901 - command-specific branches remain explicit
        self, request: GatewayRequest, command: str, params: BaseModel
    ) -> GatewayResponse | None:
        result: object
        if command == "domain_run.start":
            experiment_id = cast(ExperimentParams, params).domain_experiment_id
            manifest = self.application.reserve_grouped_run(experiment_id)
            self._begin_operation(
                request.request_id, cast(Any, manifest).domain_run_id, resume=False
            )
            return None
        elif command == "domain_run.resume":
            run_id = cast(DomainRunParams, params).domain_run_id
            manifest, _ = self.application.store.load_domain_run(run_id)
            self._begin_operation(request.request_id, manifest.domain_run_id, resume=True)
            return None
        elif command == "domain_run.status":
            run_id = cast(DomainRunParams, params).domain_run_id
            result = self.application.store.load_domain_run(run_id)[0]
        elif command == "domain_run.delete":
            if self._active_operation() is not None:
                raise DomainExtensionError(
                    "No se puede borrar durante una operación científica activa."
                )
            run_id = cast(DomainRunParams, params).domain_run_id
            result = self.application.delete_domain_run(run_id)
            self._large_result_documents = {
                digest: reference
                for digest, reference in self._large_result_documents.items()
                if reference[0] != run_id
            }
            self.attachments.authorized.clear()
            self.attachments.verified.clear()
        elif command == "domain_run.list":
            filters = cast(RunListParams, params)
            result = [
                {
                    key: value
                    for key, value in manifest.model_dump(mode="json").items()
                    if key != "cases"
                }
                for manifest, _ in self.application.store.list_domain_runs()
                if (
                    filters.domain_experiment_id is None
                    or manifest.domain_experiment_id == filters.domain_experiment_id
                )
                and (filters.domain_id is None or manifest.domain.id == filters.domain_id)
            ]
        elif command == "domain_run.result":
            run_id = cast(DomainRunParams, params).domain_run_id
            result, document = self.application.confirmed_result_document(run_id)
            inline = self._success(request.request_id, result)
            if self._message_size(inline) <= MAX_MESSAGE_BYTES:
                return inline
            digest = sha256(document).hexdigest()
            self._large_result_documents[digest] = (run_id, len(document))
            result = {
                "$desktop_transport": "domain-result-file-v1",
                "domain_run_id": run_id,
                "size_bytes": len(document),
                "sha256": digest,
            }
        elif command in {
            "domain_run.case_page",
            "domain_run.case_detail",
            "domain_run.dominators",
            "domain_run.frontier",
            "domain_run.plot_points",
            "domain_run.plot_projection",
            "domain_run.metrics",
        }:
            query_params = cast(Any, params).model_dump()
            run_id = query_params.pop("domain_run_id")
            operation = command.removeprefix("domain_run.")
            if operation == "metrics":
                result = self.application.query_result_metrics(run_id, query_params)
            else:
                result = self.application.query_fast_result(run_id, operation, query_params)
        else:  # pragma: no cover - the discriminated request union is exhaustive
            raise DomainExtensionError("Comando desconocido.")
        return self._success(request.request_id, result)

    def _begin_operation(self, request_id: str, domain_run_id: str, *, resume: bool) -> None:
        with self.active_lock:
            if self.active is not None:
                raise DomainExtensionError("Ya existe una operación científica activa.")
            if self.application.store.domain_run_active(domain_run_id):
                raise DomainExtensionError("La ejecución ya está activa.")
            operation_id = str(uuid4())
            cancellation = Event()
            emitter = OperationEmitter(self.writer, operation_id, domain_run_id)
            core = CoreCommands.open(
                self.workspace,
                observer=GatewayCoreObserver(emitter),
            )
            application = DomainApplication(
                self.workspace,
                core,
                progress_observer=GatewayGroupedObserver(emitter),
                is_cancel_requested=cancellation.is_set,
            )
            thread = Thread(
                target=self._run_operation,
                args=(emitter, application, resume),
                name=f"domain-operation-{operation_id}",
                daemon=True,
            )
            self.active = ActiveOperation(
                operation_id=operation_id,
                domain_run_id=domain_run_id,
                cancellation=cancellation,
                application=application,
                thread=thread,
            )
        response = GatewayResponse(
            request_id=request_id,
            status="accepted",
            operation_id=operation_id,
            result={"domain_run_id": domain_run_id},
            error=None,
        )
        self.writer.write(response)
        thread.start()

    def _run_operation(
        self,
        emitter: OperationEmitter,
        application: DomainApplication,
        resume: bool,
    ) -> None:
        try:
            interpreted: InterpretedRun
            if resume:
                interpreted = application.resume(emitter.domain_run_id)
            else:
                interpreted = application.execute_grouped_run(emitter.domain_run_id)
            status = interpreted.manifest.status
            emitter.emit(
                "terminal",
                {"domain_run_id": emitter.domain_run_id, "status": status},
            )
        except DomainRunCancelled:
            emitter.emit(
                "terminal",
                {"domain_run_id": emitter.domain_run_id, "status": "cancelled"},
            )
        except Exception as exc:
            error = self._gateway_error(exc)
            emitter.emit(
                "error",
                {"domain_run_id": emitter.domain_run_id, "error": error},
            )
            emitter.emit(
                "terminal",
                {"domain_run_id": emitter.domain_run_id, "status": "failed"},
            )
        finally:
            with self.active_lock:
                if self.active is not None and self.active.operation_id == emitter.operation_id:
                    self.active = None

    def _cancel(self, request: GatewayRequest, params: CancelParams) -> None:
        active = self._active_operation()
        if active is None:
            self.application.cancel_interrupted_grouped_run(
                params.domain_run_id, reason=params.reason
            )
            self.writer.write(self._success(request.request_id, {"status": "accepted"}))
            return
        if active.domain_run_id != params.domain_run_id:
            raise DomainExtensionError("Otra ejecución tiene la operación activa.")
        active.cancellation.set()
        self.writer.write(self._success(request.request_id, {"status": "accepted"}))
        try:
            active.application.cancel_active_core(reason=params.reason)
        except (DomainExtensionError, OperationalError, OSError, ValueError) as exc:
            print(
                "[gateway:cancellation] La intención fue aceptada, pero el canal CORE "
                f"no confirmó la cancelación inmediata: {exc}",
                file=sys.stderr,
                flush=True,
            )

    def _active_operation(self) -> ActiveOperation | None:
        with self.active_lock:
            return self.active

    def _template_listing(self) -> list[dict[str, str]]:
        templates: list[dict[str, str]] = []
        for domain in ("single-row-facility-layout", "inspection-route"):
            root = self.template_root / "domains" / domain
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*.json")):
                try:
                    document = json.loads(path.read_bytes())
                    config = self.application.validate_payload(self._draft_bytes(document))
                    typed_config = cast(Any, config)
                    if typed_config.domain.id != domain:
                        continue
                    templates.append(
                        {
                            "template_id": f"{domain}/{path.stem}",
                            "domain_id": domain,
                            "domain_version": typed_config.domain.version,
                            "name": path.stem,
                        }
                    )
                except (OSError, ValueError, ValidationError, DomainExtensionError):
                    continue
        root = self.workspace / "domain_templates"
        if root.is_dir() and not root.is_symlink():
            for path in sorted(root.glob("*.json")):
                try:
                    document = json.loads(path.read_bytes())
                    payload = self._draft_bytes(document)
                    config = self.application.validate_payload(payload)
                    typed_config = cast(Any, config)
                    adapter = SUPPORTED_DOMAINS[
                        (typed_config.domain.id, typed_config.domain.version)
                    ]
                    experiment_id = path.stem
                    if len(experiment_id) != 64 or any(
                        character not in "0123456789abcdef" for character in experiment_id
                    ):
                        continue
                    templates.append(
                        {
                            "template_id": f"user/{experiment_id}",
                            "domain_id": typed_config.domain.id,
                            "domain_version": typed_config.domain.version,
                            "name": adapter.display_name(config),
                            "domain_experiment_id": experiment_id,
                        }
                    )
                except (OSError, ValueError, ValidationError, DomainExtensionError):
                    continue
        return templates

    def _load_template(self, template_id: str) -> object:
        listing = {item["template_id"]: item for item in self._template_listing()}
        if template_id not in listing:
            raise DomainExtensionError("No se encontró la plantilla.", exit_code=66)
        if template_id.startswith("user/"):
            experiment_id = template_id.removeprefix("user/")
            path = self.workspace / "domain_templates" / f"{experiment_id}.json"
        else:
            domain, name = template_id.split("/", maxsplit=1)
            path = self.template_root / "domains" / domain / f"{name}.json"
        document = json.loads(path.read_bytes())
        config = self.application.validate_payload(self._draft_bytes(document))
        self.attachments.authorize(config)
        return document

    def _save_template(
        self,
        draft: Mapping[str, object],
        *,
        experiment_id: str | None = None,
    ) -> dict[str, object]:
        config = self.application.validate_payload(self._draft_bytes(draft))
        self.attachments.publish(config)
        experiment_id = experiment_id or domain_experiment_id(config)
        root = self.application.store._ensure_real_directory(self.workspace / "domain_templates")
        path = root / f"{experiment_id}.json"
        self.application.store._atomic_replace(path, pretty_json(config))
        return {"template_id": f"user/{experiment_id}", "enabled": True}

    def _set_template_for_run(self, run_id: str, enabled: bool) -> dict[str, object]:
        manifest, _ = self.application.store.load_domain_run(run_id)
        loaded = self.application.store.load(manifest.domain_experiment_id)
        experiment_id = manifest.domain_experiment_id
        root = self.workspace / "domain_templates"
        if root.exists() and (root.is_symlink() or not root.is_dir()):
            raise DomainExtensionError("domain_templates debe ser un directorio real.")
        path = root / f"{experiment_id}.json"
        if enabled:
            return self._save_template(
                loaded.record.domain_config.model_dump(mode="json"),
                experiment_id=experiment_id,
            )
        if path.exists() and path.is_file() and not path.is_symlink():
            path.unlink()
        return {"template_id": f"user/{experiment_id}", "enabled": False}

    @staticmethod
    def _draft_bytes(draft: Mapping[str, object]) -> bytes:
        return json.dumps(draft, ensure_ascii=False, separators=(",", ":")).encode()

    @staticmethod
    def _success(request_id: str, result: object) -> GatewayResponse:
        return GatewayResponse(
            request_id=request_id,
            status="success",
            operation_id=None,
            result=_json_value(result),
            error=None,
        )

    @staticmethod
    def _message_size(message: GatewayResponse) -> int:
        return len(_MESSAGE_ADAPTER.dump_json(message, exclude_none=False)) + 1

    def _read_large_result(self, digest: str, offset: int, length: int) -> str | None:
        reference = self._large_result_documents.get(digest)
        if reference is None:
            return None
        run_id, expected_size = reference
        path = self.workspace / "domain_runs" / run_id / "result.json"
        if path.is_symlink() or not path.is_file():
            raise DomainExtensionError("El resultado confirmado ya no está disponible.")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self.workspace) or resolved.stat().st_size != expected_size:
            raise DomainExtensionError("El resultado confirmado cambió durante la transferencia.")
        with resolved.open("rb") as stream:
            stream.seek(offset)
            return base64.b64encode(stream.read(length)).decode("ascii")

    def _write_protocol_error(self, request_id: str | None, code: str, message: str) -> None:
        self.writer.write(self._error_response(request_id, ValueError(message), code=code))

    def _error_response(
        self, request_id: str | None, exc: Exception, *, code: str | None = None
    ) -> GatewayResponse:
        return GatewayResponse(
            request_id=self._safe_request_id(request_id),
            status="error",
            operation_id=None,
            result=None,
            error=self._gateway_error(exc, code=code),
        )

    @staticmethod
    def _safe_request_id(request_id: str | None) -> str:
        if request_id is not None:
            try:
                parsed = UUID(request_id)
            except ValueError:
                pass
            else:
                if parsed.version == 4 and str(parsed) == request_id:
                    return request_id
        return str(uuid4())

    @staticmethod
    def _gateway_error(exc: Exception, *, code: str | None = None) -> GatewayError:
        if code is None and isinstance(exc, OperationalError):
            code = exc.code.value
        if code is None and isinstance(exc, DomainExtensionError):
            code = "DOMAIN_ERROR"
        return GatewayError(
            code=code or "INTERNAL_ERROR",
            message=str(exc)[:512] or type(exc).__name__,
            details={"exception_type": type(exc).__name__},
        )
