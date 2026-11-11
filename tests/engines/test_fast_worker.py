from __future__ import annotations

from math import factorial

import pytest

from tesis_proyect.runner.fast_worker import (
    FastCountingWorker,
    FastWorkerCancelled,
    FastWorkerError,
    _decimal_to_integer,
    _integer_to_decimal,
    _json_frame,
)


def test_persistent_worker_reuses_process_for_distinct_exact_requests() -> None:
    with FastCountingWorker(timeout_ms=10_000) as worker:
        assert worker.count(4, 1, 1) == 6
        assert worker.count(10, 0, 0) == factorial(10) // 2


def test_persistent_worker_preserves_counts_beyond_javascript_safe_integer() -> None:
    with FastCountingWorker(timeout_ms=10_000) as worker:
        assert worker.count(171, 0, 0) == factorial(171) // 2


def test_decimal_codec_handles_values_larger_than_python_string_conversion_limit() -> None:
    value = 10**5_000 + 123
    digits = _integer_to_decimal(value)
    assert digits == f"1{'0' * 4_997}123"
    assert _decimal_to_integer(digits) == value


def test_worker_checks_cancellation_between_requests() -> None:
    with (
        FastCountingWorker(timeout_ms=10_000, is_cancel_requested=lambda: True) as worker,
        pytest.raises(FastWorkerCancelled),
    ):
        worker.count(4, 1, 1)


def test_worker_returns_invalid_input_as_a_run_level_failure() -> None:
    with (
        FastCountingWorker(timeout_ms=10_000) as worker,
        pytest.raises(FastWorkerError, match="ValueError"),
    ):
        worker.count(3, 2, 2)


def test_worker_frame_enforces_byte_limit() -> None:
    with pytest.raises(FastWorkerError, match="byte limit"):
        _json_frame({"value": "x" * 1_000}, 64)
