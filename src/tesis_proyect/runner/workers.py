from __future__ import annotations

import json
import multiprocessing
import struct
import sys
import traceback
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from multiprocessing.connection import Connection, wait
from time import monotonic, perf_counter_ns
from typing import Any, Literal, cast

from tesis_proyect.engines.exact import run_exact
from tesis_proyect.engines.reference import EngineCancelled, count_reference
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import AttemptMetrics
from tesis_proyect.models.enums import ErrorCode, StageId
from tesis_proyect.models.factories import structured_error
from tesis_proyect.models.protocols import WorkerRequest, WorkerResponse
from tesis_proyect.models.scientific import CountingResult
from tesis_proyect.runner.worker_protocol import decode_frame, encode_frame

_PROGRESS_DIGITS = 309
_PROGRESS_FRAME = struct.Struct(f">BHH{_PROGRESS_DIGITS}s{_PROGRESS_DIGITS}s")
_PROGRESS_VERSION = 1
_MAX_PROGRESS_INTEGER = int(sys.float_info.max)
_FAULT_MAX_BYTES = 32_768
_FAULT_PHASES = frozenset(
    {"decode_request", "execute_engine", "build_response", "send_response", "progress_telemetry"}
)
type Termination = Literal["not_applicable", "cooperative", "forced"]


@dataclass(frozen=True)
class WorkerFault:
    phase: str
    exception_type: str
    message: str
    traceback: str


class WorkerExecutionFailure(OperationalError):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        termination: Termination,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message)
        self.termination = termination
        self.details = details


def _worker_entry(  # noqa: C901 - explicit worker lifecycle state machine
    channel: Connection,
    cancellation: Connection,
    max_bytes: int,
    progress_channel: Connection | None = None,
    fault_channel: Connection | None = None,
) -> None:
    started = perf_counter_ns()
    try:
        try:
            request = decode_frame(channel.recv_bytes(), WorkerRequest, max_bytes)
        except Exception as exc:
            _send_fault(fault_channel, "decode_request", exc)
            return

        try:
            if request.stage == "run_exact_method":
                result: CountingResult = run_exact(request.instance)
            else:
                last_progress_ns = 0

                def report_progress(completed: int, total: int) -> None:
                    nonlocal last_progress_ns
                    now = perf_counter_ns()
                    if completed not in {0, total} and now - last_progress_ns < 100_000_000:
                        return
                    last_progress_ns = now
                    frame = _encode_progress(completed, total)
                    if progress_channel is None or frame is None:
                        return
                    try:
                        progress_channel.send_bytes(frame)
                    except Exception as exc:
                        _send_fault(fault_channel, "progress_telemetry", exc)

                result = count_reference(
                    request.instance,
                    reference_max_n=request.limits.reference_max_n,
                    cancelled=cancellation.poll,
                    progress=report_progress,
                )
            response = WorkerResponse(
                schema_version="1.0.0",
                request_id=request.request_id,
                run_id=request.run_id,
                stage=request.stage,
                status=result.status,
                result=result,
                error=None,
                metrics=result.metrics,
            )
        except EngineCancelled:
            response = _cancelled_response(request, started)
        except Exception as exc:
            _send_fault(fault_channel, "execute_engine", exc)
            try:
                response = _unexpected_failure_response(request, started, exc)
            except Exception as build_exc:
                _send_fault(fault_channel, "build_response", build_exc)
                return

        try:
            channel.send_bytes(encode_frame(response, max_bytes))
        except Exception as exc:
            _send_fault(fault_channel, "send_response", exc)
    finally:
        channel.close()
        cancellation.close()
        if progress_channel is not None:
            progress_channel.close()
        if fault_channel is not None:
            fault_channel.close()


def execute_worker(  # noqa: C901 - explicit parent IPC state machine
    request: WorkerRequest,
    *,
    timeout_ms: int,
    cancellation_grace_ms: int,
    cancellation_connection: Any | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    diagnostic_callback: Callable[[str], None] | None = None,
    debug: bool = False,
) -> tuple[WorkerResponse, Termination]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    cancel_child, cancel_parent = context.Pipe(duplex=False)
    progress_parent, progress_child = context.Pipe(duplex=False)
    fault_parent, fault_child = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker_entry,
        args=(child, cancel_child, request.limits.max_message_bytes, progress_child, fault_child),
        daemon=False,
    )
    process.start()
    child.close()
    cancel_child.close()
    progress_child.close()
    fault_child.close()
    faults: list[WorkerFault] = []
    try:
        parent.send_bytes(encode_frame(request, request.limits.max_message_bytes))
        parent_waitable = cast(Connection, parent)
        progress_waitable = cast(Connection, progress_parent)
        fault_waitable = cast(Connection, fault_parent)
        waitables: list[Any] = [parent_waitable, progress_waitable, fault_waitable]
        if cancellation_connection is not None:
            waitables.append(cancellation_connection)
        deadline = monotonic() + timeout_ms / 1000
        while True:
            ready = wait(waitables, max(0.0, deadline - monotonic()))
            if fault_waitable in ready:
                if not _receive_fault(fault_parent, faults):
                    waitables.remove(fault_waitable)
                continue
            if parent_waitable in ready:
                try:
                    response = _validated_response(parent.recv_bytes(), request)
                except EOFError:
                    process.join()
                    _drain_faults(fault_parent, faults)
                    _emit_faults(faults, diagnostic_callback, debug=debug)
                    raise _termination_failure(faults) from None
                process.join()
                _drain_faults(fault_parent, faults)
                _emit_faults(faults, diagnostic_callback, debug=debug)
                return response, "not_applicable"
            if cancellation_connection is not None and cancellation_connection in ready:
                cancellation_connection.recv_bytes()
                cancel_parent.send_bytes(b"\x01")
                if parent.poll(cancellation_grace_ms / 1000):
                    try:
                        response = _validated_response(parent.recv_bytes(), request)
                    except EOFError:
                        process.join()
                        _drain_faults(fault_parent, faults)
                        _emit_faults(faults, diagnostic_callback, debug=debug)
                        raise _termination_failure(faults) from None
                    process.join()
                    _drain_faults(fault_parent, faults)
                    _emit_faults(faults, diagnostic_callback, debug=debug)
                    return response, "cooperative"
                process.terminate()
                process.join()
                _drain_faults(fault_parent, faults)
                _emit_faults(faults, diagnostic_callback, debug=debug)
                raise WorkerExecutionFailure(
                    ErrorCode.RUN_CANCELLED, "Worker cancellation was forced.", "forced"
                )
            if progress_waitable in ready:
                if not _forward_progress(progress_parent, progress_callback):
                    waitables.remove(progress_waitable)
                continue
            break
        cancel_parent.send_bytes(b"\x01")
        process.join(cancellation_grace_ms / 1000)
        termination: Termination = "cooperative"
        if process.is_alive():
            process.terminate()
            process.join()
            termination = "forced"
        _drain_faults(fault_parent, faults)
        _emit_faults(faults, diagnostic_callback, debug=debug)
        raise WorkerExecutionFailure(
            ErrorCode.STAGE_TIMEOUT, f"Worker timed out ({termination}).", termination
        )
    finally:
        _ensure_stopped(process)
        parent.close()
        cancel_parent.close()
        progress_parent.close()
        fault_parent.close()


def _cancelled_response(request: WorkerRequest, started: int) -> WorkerResponse:
    duration = (perf_counter_ns() - started) // 1_000_000
    return WorkerResponse(
        schema_version="1.0.0",
        request_id=request.request_id,
        run_id=request.run_id,
        stage=request.stage,
        status="failed",
        result=None,
        error=structured_error(
            ErrorCode.RUN_CANCELLED,
            "Worker cancellation was requested.",
            stage=StageId(request.stage),
        ),
        metrics=_failure_metrics(request, duration),
    )


def _unexpected_failure_response(
    request: WorkerRequest, started: int, exc: Exception
) -> WorkerResponse:
    duration = (perf_counter_ns() - started) // 1_000_000
    return WorkerResponse(
        schema_version="1.0.0",
        request_id=request.request_id,
        run_id=request.run_id,
        stage=request.stage,
        status="failed",
        result=None,
        error=structured_error(
            ErrorCode.INTERNAL_ERROR,
            "Worker execution failed unexpectedly.",
            stage=StageId(request.stage),
            details={"phase": "execute_engine", "exception_type": type(exc).__name__},
        ),
        metrics=_failure_metrics(request, duration),
    )


def _failure_metrics(request: WorkerRequest, duration: int) -> AttemptMetrics:
    return AttemptMetrics(
        duration_ms=duration,
        worker_duration_ms=duration,
        candidates_examined=None,
        peak_memory_bytes=None,
        producer=request.producer,
    )


def _encode_progress(completed: int, total: int) -> bytes | None:
    if (
        isinstance(completed, bool)
        or isinstance(total, bool)
        or not isinstance(completed, int)
        or not isinstance(total, int)
        or completed < 0
        or total < 0
        or completed > total
        or completed > _MAX_PROGRESS_INTEGER
        or total > _MAX_PROGRESS_INTEGER
    ):
        return None
    completed_bytes = str(completed).encode("ascii")
    total_bytes = str(total).encode("ascii")
    return _PROGRESS_FRAME.pack(
        _PROGRESS_VERSION,
        len(completed_bytes),
        len(total_bytes),
        completed_bytes,
        total_bytes,
    )


def _decode_progress(frame: bytes) -> tuple[int, int] | None:
    if len(frame) != _PROGRESS_FRAME.size:
        return None
    version, completed_length, total_length, completed_raw, total_raw = _PROGRESS_FRAME.unpack(
        frame
    )
    if (
        version != _PROGRESS_VERSION
        or completed_length < 1
        or total_length < 1
        or completed_length > _PROGRESS_DIGITS
        or total_length > _PROGRESS_DIGITS
        or any(completed_raw[completed_length:])
        or any(total_raw[total_length:])
    ):
        return None
    completed_text = completed_raw[:completed_length]
    total_text = total_raw[:total_length]
    if not _canonical_decimal(completed_text) or not _canonical_decimal(total_text):
        return None
    completed = int(completed_text)
    total = int(total_text)
    if completed > total or total > _MAX_PROGRESS_INTEGER:
        return None
    return completed, total


def _canonical_decimal(value: bytes) -> bool:
    return value == b"0" or (value[:1] in b"123456789" and value.isdigit())


def _send_fault(channel: Connection | None, phase: str, exc: Exception) -> None:
    if channel is None:
        return
    fault = WorkerFault(
        phase=phase,
        exception_type=type(exc).__name__,
        message=_truncate_utf8(str(exc), 1_024),
        traceback=_truncate_utf8("".join(traceback.format_exception(exc)), 8_192),
    )
    with suppress(Exception):
        channel.send_bytes(_encode_fault(fault))


def _encode_fault(fault: WorkerFault) -> bytes:
    frame = json.dumps(
        {
            "phase": fault.phase,
            "exception_type": fault.exception_type,
            "message": fault.message,
            "traceback": fault.traceback,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(frame) > _FAULT_MAX_BYTES:
        raise ValueError("Worker fault frame exceeds its internal bound.")
    return frame


def _decode_fault(frame: bytes) -> WorkerFault | None:
    if len(frame) > _FAULT_MAX_BYTES:
        return None
    try:
        value = json.loads(frame)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or set(value) != {
        "phase",
        "exception_type",
        "message",
        "traceback",
    }:
        return None
    if not all(isinstance(item, str) for item in value.values()):
        return None
    if value["phase"] not in _FAULT_PHASES:
        return None
    return WorkerFault(**value)


def _truncate_utf8(value: str, max_bytes: int) -> str:
    return value.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")


def _receive_fault(connection: Any, faults: list[WorkerFault]) -> bool:
    try:
        frame = connection.recv_bytes(_FAULT_MAX_BYTES)
    except (EOFError, OSError):
        return False
    fault = _decode_fault(frame)
    if fault is not None:
        faults.append(fault)
    return True


def _drain_faults(connection: Any, faults: list[WorkerFault]) -> None:
    with suppress(OSError):
        while connection.poll():
            if not _receive_fault(connection, faults):
                break


def _emit_faults(
    faults: list[WorkerFault],
    callback: Callable[[str], None] | None,
    *,
    debug: bool,
) -> None:
    if callback is None:
        return
    for fault in faults:
        message = f"Worker fault: phase={fault.phase} exception_type={fault.exception_type}"
        if debug:
            message = f"{message} message={fault.message}\n{fault.traceback}"
        with suppress(Exception):
            callback(message)


def _termination_failure(faults: list[WorkerFault]) -> WorkerExecutionFailure:
    fault = faults[-1] if faults else None
    if fault is not None and fault.phase == "decode_request":
        code, message = ErrorCode.WORKER_PROTOCOL_ERROR, "Worker could not decode its request."
    elif fault is not None and fault.phase in {"execute_engine", "build_response"}:
        code, message = ErrorCode.INTERNAL_ERROR, "Worker failed before producing a response."
    else:
        code, message = ErrorCode.WORKER_TERMINATED, "Worker terminated without a response."
    details = (
        {"phase": fault.phase, "exception_type": fault.exception_type}
        if fault is not None
        else None
    )
    return WorkerExecutionFailure(code, message, "forced", details=details)


def _validated_response(frame: bytes, request: WorkerRequest) -> WorkerResponse:
    response = decode_frame(frame, WorkerResponse, request.limits.max_message_bytes)
    if (
        response.request_id != request.request_id
        or response.run_id != request.run_id
        or response.stage != request.stage
    ):
        raise OperationalError(
            ErrorCode.WORKER_PROTOCOL_ERROR, "Worker response identity mismatch."
        )
    return response


def _forward_progress(
    progress_connection: Any,
    callback: Callable[[int, int], None] | None,
) -> bool:
    try:
        frame = progress_connection.recv_bytes()
    except (EOFError, OSError):
        return False
    progress = _decode_progress(frame)
    if progress is not None and callback is not None:
        with suppress(Exception):
            callback(*progress)
    return True


def _ensure_stopped(process: Any) -> None:
    if process.is_alive():
        process.terminate()
        process.join()
