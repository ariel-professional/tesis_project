import multiprocessing
from math import factorial
from uuid import UUID

import pytest

from tesis_proyect.domain.hashing import instance_hash
from tesis_proyect.engines.exact import count_closed_form, run_exact
from tesis_proyect.engines.reference import EngineCancelled, count_reference
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import InlineMetadata, ProducerRef
from tesis_proyect.models.enums import ErrorCode
from tesis_proyect.models.execution import Instance
from tesis_proyect.models.protocols import WorkerLimits, WorkerRequest, WorkerResponse
from tesis_proyect.runner.worker_protocol import decode_frame, encode_frame
from tesis_proyect.runner.workers import (
    WorkerFault,
    _decode_fault,
    _decode_progress,
    _emit_faults,
    _encode_progress,
    _worker_entry,
    execute_worker,
)

pytestmark = [pytest.mark.integration, pytest.mark.platform]

RUN_ID = "12345678-1234-4234-8234-123456789abc"
REQUEST_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def instance(n: int, raw: list[tuple[int, int]]) -> Instance:
    edges = tuple(sorted(raw))
    return Instance(
        schema_version="1.0.0",
        n=n,
        vertex_base=1,
        edges=list(edges),
        source_metadata=InlineMetadata(kind="inline"),
        instance_hash=instance_hash(n, edges),
    )


@pytest.mark.parametrize(
    ("n", "edges", "expected"),
    [
        (1, [], 1),
        (2, [], 1),
        (3, [], 3),
        (4, [], 12),
        (3, [(1, 2)], 2),
        (4, [(1, 2)], 6),
        (4, [(1, 2), (3, 4)], 4),
        (4, [(1, 2), (2, 3)], 2),
        (5, [(1, 2), (3, 4)], 12),
        (5, [(1, 2), (2, 3), (3, 4)], 2),
        (5, [(1, 2), (2, 3), (3, 4), (4, 5)], 1),
        (6, [(1, 2), (2, 3), (4, 5)], 12),
        (7, [(1, 2), (2, 3), (3, 4), (5, 6)], 12),
    ],
)
def test_independent_reference_baselines(
    n: int, edges: list[tuple[int, int]], expected: int
) -> None:
    result = count_reference(instance(n, edges), reference_max_n=10)
    assert result.status == "success"
    assert result.value == expected


def test_reference_and_exact_own_skips() -> None:
    large = instance(12, [(1, 2), (3, 4), (5, 6)])
    reference = count_reference(large, reference_max_n=10)
    exact = run_exact(large)
    assert reference.status == "skipped"
    assert reference.skip.code == "BRUTE_FORCE_LIMIT_EXCEEDED"
    assert exact.status == "success"
    assert exact.value == 1_451_520


@pytest.mark.parametrize(
    ("n", "c", "m", "expected"),
    [
        (1, 0, 0, 1),
        (2, 0, 0, 1),
        (3, 0, 0, 3),
        (4, 1, 1, 6),
        (6, 2, 3, 12),
        (50, 0, 0, factorial(50) // 2),
    ],
)
def test_closed_form_values(n: int, c: int, m: int, expected: int) -> None:
    assert count_closed_form(n, c, m) == expected


@pytest.mark.parametrize(
    "values",
    [
        (0, 0, 0),
        (3, -1, 0),
        (3, 0, -1),
        (3, 3, 1),
        (3, 2, 1),
        (3, 0, 1),
        (3, 2, 2),
    ],
)
def test_closed_form_rejects_impossible_ranges(values: tuple[int, int, int]) -> None:
    with pytest.raises(ValueError):
        count_closed_form(*values)


@pytest.mark.parametrize("value", [True, 1.0, "1"])
def test_closed_form_rejects_non_integer_types(value: object) -> None:
    with pytest.raises(TypeError):
        count_closed_form(value, 0, 0)  # type: ignore[arg-type]


def test_reference_observes_cooperative_cancellation() -> None:
    with pytest.raises(EngineCancelled):
        count_reference(instance(5, []), reference_max_n=10, cancelled=lambda: True)


def test_reference_reports_monotonic_bounded_progress() -> None:
    updates: list[tuple[int, int]] = []
    result = count_reference(
        instance(7, []),
        reference_max_n=10,
        progress=lambda completed, total: updates.append((completed, total)),
    )
    assert result.status == "success"
    assert updates[0][0] == 0
    assert updates[-1][0] == updates[-1][1] == result.metrics.candidates_examined
    assert [completed for completed, _ in updates] == sorted(completed for completed, _ in updates)
    assert all(0 <= completed <= total for completed, total in updates)


def request(stage: str = "run_reference_method", n: int = 4) -> WorkerRequest:
    return WorkerRequest(
        schema_version="1.0.0",
        request_id=REQUEST_ID,
        run_id=RUN_ID,
        stage=stage,
        instance=instance(n, []),
        producer=ProducerRef(id="bruteforce-python", version="1"),
        limits=WorkerLimits(
            timeout_ms=30000,
            max_message_bytes=65536,
            reference_max_n=max(10, n),
        ),
        counting_convention="undirected_paths_reverse_identified",
    )


def test_worker_frame_round_trip_and_bounds() -> None:
    message = request()
    frame = encode_frame(message, 65536)
    assert int.from_bytes(frame[:4], "big") == len(frame) - 4
    assert decode_frame(frame, WorkerRequest, 65536) == message
    for invalid in (b"", b"\x00\x00\x00\x04{}", b"\x00\x01\x00\x00"):
        with pytest.raises(OperationalError):
            decode_frame(invalid, WorkerRequest, 1024)
    with pytest.raises(OperationalError):
        encode_frame(message, 10)


@pytest.mark.parametrize("stage", ["run_exact_method", "run_reference_method"])
def test_spawn_worker_returns_validated_response(stage: str) -> None:
    response, termination = execute_worker(
        request(stage), timeout_ms=30000, cancellation_grace_ms=1000
    )
    assert isinstance(response, WorkerResponse)
    assert response.request_id == REQUEST_ID
    assert response.status in {"success", "skipped"}
    assert termination == "not_applicable"


def test_spawn_reference_n10_finishes_before_the_operational_timeout() -> None:
    response, termination = execute_worker(
        request(stage="run_reference_method", n=10),
        timeout_ms=10_000,
        cancellation_grace_ms=1_000,
    )

    assert response.status == "success"
    assert response.result is not None
    assert response.result.value == factorial(10) // 2
    assert response.metrics.candidates_examined == factorial(10) // 2
    assert termination == "not_applicable"


def test_spawn_worker_forwards_ephemeral_progress() -> None:
    updates: list[tuple[int, int]] = []
    response, _ = execute_worker(
        request(n=7),
        timeout_ms=30000,
        cancellation_grace_ms=1000,
        progress_callback=lambda completed, total: updates.append((completed, total)),
    )
    assert response.status == "success"
    assert updates
    assert updates[0][0] == 0
    assert updates[-1][0] == updates[-1][1]


@pytest.mark.parametrize("n", [50, 170])
def test_progress_codec_preserves_large_exact_totals(n: int) -> None:
    total = factorial(n) // 2
    frame = _encode_progress(0, total)
    assert frame is not None
    assert _decode_progress(frame) == (0, total)


def test_progress_codec_degrades_for_totals_above_finite_float_range() -> None:
    assert _encode_progress(0, factorial(171) // 2) is None


def test_n_50_timeout_is_not_misreported_as_worker_termination() -> None:
    with pytest.raises(OperationalError) as failure:
        execute_worker(request(n=50), timeout_ms=50, cancellation_grace_ms=0)
    assert failure.value.code == ErrorCode.STAGE_TIMEOUT


def test_worker_timeout_does_not_invent_result() -> None:
    with pytest.raises(OperationalError) as failure:
        execute_worker(request(n=10), timeout_ms=1, cancellation_grace_ms=0)
    assert failure.value.code == "STAGE_TIMEOUT"


def test_worker_observes_runner_cancellation_channel() -> None:
    context = multiprocessing.get_context("spawn")
    cancellation_reader, cancellation_writer = context.Pipe(duplex=False)
    try:
        cancellation_writer.send_bytes(b"\x01")
        response, termination = execute_worker(
            request(n=10),
            timeout_ms=30000,
            cancellation_grace_ms=5000,
            cancellation_connection=cancellation_reader,
        )
    finally:
        cancellation_reader.close()
        cancellation_writer.close()
    assert response.status == "failed"
    assert response.error is not None
    assert response.error.code == ErrorCode.RUN_CANCELLED
    assert termination == "cooperative"


class FakeChannel:
    def __init__(self, incoming: bytes, *, fail_send: bool = False) -> None:
        self.incoming = incoming
        self.outgoing: bytes | None = None
        self.fail_send = fail_send
        self.closed = False

    def recv_bytes(self) -> bytes:
        return self.incoming

    def send_bytes(self, payload: bytes) -> None:
        if self.fail_send:
            raise OSError("injected send failure")
        self.outgoing = payload

    def close(self) -> None:
        self.closed = True


class FakeCancellation:
    def __init__(self, cancelled: bool) -> None:
        self.cancelled = cancelled
        self.closed = False

    def poll(self) -> bool:
        return self.cancelled

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize(
    ("stage", "cancelled", "expected"),
    [
        ("run_exact_method", False, "success"),
        ("run_reference_method", False, "success"),
        ("run_reference_method", True, "failed"),
    ],
)
def test_worker_entry_produces_one_framed_response(
    stage: str, cancelled: bool, expected: str
) -> None:
    message = request(stage)
    channel = FakeChannel(encode_frame(message, 65536))
    cancellation = FakeCancellation(cancelled)
    _worker_entry(channel, cancellation, 65536)  # type: ignore[arg-type]
    assert channel.outgoing is not None
    response = decode_frame(channel.outgoing, WorkerResponse, 65536)
    assert response.status == expected
    assert channel.closed and cancellation.closed


def test_worker_entry_suppresses_invalid_input_and_send_failures() -> None:
    invalid = FakeChannel(b"invalid")
    cancellation = FakeCancellation(False)
    invalid_fault = FakeChannel(b"")
    _worker_entry(  # type: ignore[arg-type]
        invalid, cancellation, 65536, fault_channel=invalid_fault
    )
    assert invalid.outgoing is None
    assert invalid_fault.outgoing is not None
    assert _decode_fault(invalid_fault.outgoing).phase == "decode_request"
    failing = FakeChannel(encode_frame(request(), 65536), fail_send=True)
    send_fault = FakeChannel(b"")
    _worker_entry(  # type: ignore[arg-type]
        failing, FakeCancellation(False), 65536, fault_channel=send_fault
    )
    assert failing.outgoing is None
    assert send_fault.outgoing is not None
    assert _decode_fault(send_fault.outgoing).phase == "send_response"


def test_progress_transport_failure_does_not_abort_computation() -> None:
    channel = FakeChannel(encode_frame(request(), 65536))
    progress = FakeChannel(b"", fail_send=True)
    faults = FakeChannel(b"")
    _worker_entry(  # type: ignore[arg-type]
        channel,
        FakeCancellation(False),
        65536,
        progress_channel=progress,
        fault_channel=faults,
    )
    assert channel.outgoing is not None
    response = decode_frame(channel.outgoing, WorkerResponse, 65536)
    assert response.status == "success"
    assert faults.outgoing is not None
    assert _decode_fault(faults.outgoing).phase == "progress_telemetry"


def test_unexpected_engine_failure_is_structured_and_traced(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("injected engine detail")

    monkeypatch.setattr("tesis_proyect.runner.workers.count_reference", fail)
    channel = FakeChannel(encode_frame(request(), 65536))
    faults = FakeChannel(b"")
    _worker_entry(  # type: ignore[arg-type]
        channel, FakeCancellation(False), 65536, fault_channel=faults
    )
    assert channel.outgoing is not None
    response = decode_frame(channel.outgoing, WorkerResponse, 65536)
    assert response.status == "failed"
    assert response.error is not None
    assert response.error.code == ErrorCode.INTERNAL_ERROR
    assert response.error.details == {
        "phase": "execute_engine",
        "exception_type": "RuntimeError",
    }
    assert faults.outgoing is not None
    fault = _decode_fault(faults.outgoing)
    assert fault is not None
    assert "injected engine detail" in fault.traceback


def test_fault_logging_respects_normal_and_debug_policy() -> None:
    fault = WorkerFault(
        phase="execute_engine",
        exception_type="RuntimeError",
        message="private detail",
        traceback="Traceback: private detail",
    )
    normal: list[str] = []
    debug: list[str] = []
    _emit_faults([fault], normal.append, debug=False)
    _emit_faults([fault], debug.append, debug=True)
    assert normal == ["Worker fault: phase=execute_engine exception_type=RuntimeError"]
    assert "private detail" not in normal[0]
    assert "private detail" in debug[0]
    assert "Traceback:" in debug[0]


def test_uuid_constants_are_canonical_v4() -> None:
    assert UUID(RUN_ID).version == UUID(REQUEST_ID).version == 4
