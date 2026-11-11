from __future__ import annotations

from collections.abc import Callable
from itertools import permutations
from math import factorial
from time import perf_counter_ns

from tesis_proyect.models.common import AttemptMetrics, ProducerRef
from tesis_proyect.models.enums import CountingConvention, ErrorCode
from tesis_proyect.models.execution import Instance, SkipCause
from tesis_proyect.models.scientific import (
    CountingResult,
    CountingSkipped,
    CountingSuccess,
)

_CHECK_INTERVAL = 1_024


class EngineCancelled(Exception):
    pass


def _raise_if_cancelled(cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise EngineCancelled


def count_reference(
    instance: Instance,
    *,
    reference_max_n: int,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[int, int], None] | None = None,
) -> CountingResult:
    producer = ProducerRef(id="bruteforce-python", version="1")
    if instance.n > reference_max_n:
        return CountingSkipped(
            schema_version="1.0.0",
            status="skipped",
            value=None,
            engine=producer,
            formulation="canonical-permutation-enumeration-v1",
            counting_convention=CountingConvention.UNDIRECTED_PATHS_REVERSE_IDENTIFIED,
            metrics=AttemptMetrics(
                duration_ms=0,
                worker_duration_ms=0,
                candidates_examined=0,
                peak_memory_bytes=None,
                producer=producer,
            ),
            instance_hash=instance.instance_hash,
            skip=SkipCause(
                kind="own",
                code=ErrorCode.BRUTE_FORCE_LIMIT_EXCEEDED,
                message="The reference method limit was exceeded.",
            ),
        )
    started = perf_counter_ns()
    total = 1 if instance.n == 1 else factorial(instance.n) // 2
    if progress is not None:
        progress(0, total)
    required = tuple(instance.edges)
    positions = [0] * (instance.n + 1)
    count = 0
    examined = 0
    _raise_if_cancelled(cancelled)
    for candidate in permutations(range(1, instance.n + 1)):
        # For a permutation with distinct endpoints, comparison with its reverse
        # is decided by the first and last vertices. This keeps one orientation
        # without allocating the reversed tuple for every candidate.
        if candidate[0] > candidate[-1]:
            continue
        examined += 1
        if examined % _CHECK_INTERVAL == 0:
            _raise_if_cancelled(cancelled)
            if progress is not None:
                progress(examined, total)
        for index, vertex in enumerate(candidate):
            positions[vertex] = index
        if all(abs(positions[first] - positions[second]) == 1 for first, second in required):
            count += 1
    _raise_if_cancelled(cancelled)
    duration_ms = (perf_counter_ns() - started) // 1_000_000
    if progress is not None:
        progress(examined, total)
    metrics = AttemptMetrics(
        duration_ms=duration_ms,
        worker_duration_ms=duration_ms,
        candidates_examined=examined,
        peak_memory_bytes=None,
        producer=producer,
    )
    return CountingSuccess(
        schema_version="1.0.0",
        status="success",
        value=count,
        engine=producer,
        formulation="canonical-permutation-enumeration-v1",
        counting_convention=CountingConvention.UNDIRECTED_PATHS_REVERSE_IDENTIFIED,
        metrics=metrics,
        instance_hash=instance.instance_hash,
        skip=None,
    )
