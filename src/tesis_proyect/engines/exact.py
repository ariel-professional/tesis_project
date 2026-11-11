from math import factorial
from time import perf_counter_ns

from tesis_proyect.domain.hashing import instance_hash
from tesis_proyect.models.common import AttemptMetrics, ProducerRef
from tesis_proyect.models.enums import CountingConvention
from tesis_proyect.models.execution import Instance
from tesis_proyect.models.scientific import CountingSuccess

EXACT_PRODUCER = ProducerRef(id="linear-forest-closed-form", version="1")
EXACT_FORMULATION = "linear-forest-block-permutation-v1"


def count_closed_form(n: int, c: int, m: int) -> int:
    """Count undirected Hamiltonian paths containing a valid linear forest.

    ``c`` is the number of forest components that contain edges and ``m`` is
    the total number of prescribed edges. This function intentionally knows
    nothing about the graph represented by those values.
    """
    if any(type(value) is not int for value in (n, c, m)):
        raise TypeError("n, c, and m must be integers")
    if n < 1 or c < 0 or m < 0 or m > n - 1 or c > m:
        raise ValueError("n, c, and m are outside the valid linear-forest ranges")
    if (m == 0 and c != 0) or (m > 0 and (c == 0 or n < m + c)):
        raise ValueError("n, c, and m cannot describe a linear forest")
    if n == 1:
        if (c, m) != (0, 0):
            raise ValueError("the one-vertex forest must have c=m=0")
        return 1
    return int((2**c * factorial(n - m)) // 2)


def run_exact(instance: Instance) -> CountingSuccess:
    started = perf_counter_ns()
    parents = list(range(instance.n + 1))

    def find(vertex: int) -> int:
        while parents[vertex] != vertex:
            parents[vertex] = parents[parents[vertex]]
            vertex = parents[vertex]
        return vertex

    for first, second in instance.edges:
        root = find(first)
        other = find(second)
        if root != other:
            parents[other] = root
    edge_components = {find(first) for first, _ in instance.edges}
    c = len(edge_components)
    m = len(instance.edges)
    value = count_closed_form(instance.n, c, m)
    duration = (perf_counter_ns() - started) // 1_000_000
    return CountingSuccess(
        schema_version="1.0.0",
        status="success",
        value=value,
        engine=EXACT_PRODUCER,
        formulation=EXACT_FORMULATION,
        counting_convention=CountingConvention.UNDIRECTED_PATHS_REVERSE_IDENTIFIED,
        metrics=AttemptMetrics(
            duration_ms=duration,
            worker_duration_ms=duration,
            candidates_examined=0,
            peak_memory_bytes=None,
            producer=EXACT_PRODUCER,
        ),
        instance_hash=instance_hash(instance.n, tuple(instance.edges)),
        skip=None,
    )
