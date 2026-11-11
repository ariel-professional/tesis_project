from __future__ import annotations

import hashlib
from typing import cast

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.base import CandidateJsonValue
from tesis_proyect.models.common import (
    FileMetadata,
    GeneratorMetadata,
    InlineMetadata,
)
from tesis_proyect.models.config import (
    CycleParameters,
    EdgeCountParameters,
    EmptyParameters,
    ExperimentConfig,
    FileSource,
    GeneratorSource,
    InlineSource,
    MultiplePathsParameters,
    OutOfRangeParameters,
)
from tesis_proyect.models.enums import ErrorCode
from tesis_proyect.models.execution import (
    InstanceCandidate,
)
from tesis_proyect.persistence.json_store import JsonStore

BUILTIN_V1_COUNTER_ASCII = b"0"


def _vertex_permutation(n: int, seed: int) -> list[int]:
    prefix = b"builtin-v1\0" + str(seed).encode("ascii") + b"\0"
    return sorted(
        range(1, n + 1),
        key=lambda vertex: (
            hashlib.sha256(
                prefix + BUILTIN_V1_COUNTER_ASCII + b"\0" + str(vertex).encode("ascii")
            ).digest(),
            vertex,
        ),
    )


def _path(vertices: list[int]) -> list[list[int]]:
    return [[vertices[index], vertices[index + 1]] for index in range(len(vertices) - 1)]


def _candidate_edges(edges: list[list[int]]) -> list[CandidateJsonValue]:
    return cast(list[CandidateJsonValue], edges)


def generate_edges(config: ExperimentConfig, source: GeneratorSource) -> list[CandidateJsonValue]:
    vertices = _vertex_permutation(config.n, source.seed)
    family = source.family
    params = source.parameters
    if family == "empty":
        assert isinstance(params, EmptyParameters)
        return []
    if family == "matching":
        assert isinstance(params, EdgeCountParameters)
        return _candidate_edges(
            [[vertices[2 * index], vertices[2 * index + 1]] for index in range(params.edge_count)]
        )
    if family == "single_path":
        assert isinstance(params, EdgeCountParameters)
        return _candidate_edges(_path(vertices[: params.edge_count + 1]))
    if family == "multiple_paths":
        assert isinstance(params, MultiplePathsParameters)
        edges: list[CandidateJsonValue] = []
        offset = 0
        for length in params.component_edge_lengths:
            edges.extend(_candidate_edges(_path(vertices[offset : offset + length + 1])))
            offset += length + 1
        return edges
    return _generate_invalid(config, source, vertices)


def _generate_invalid(
    config: ExperimentConfig,
    source: GeneratorSource,
    vertices: list[int],
) -> list[CandidateJsonValue]:
    family = source.family
    params = source.parameters
    if family == "invalid_loop":
        return _candidate_edges([[vertices[0], vertices[0]]])
    if family == "invalid_duplicate":
        return _candidate_edges([[vertices[0], vertices[1]], [vertices[1], vertices[0]]])
    if family == "invalid_vertex_out_of_range":
        assert isinstance(params, OutOfRangeParameters)
        raw = [[0, vertices[0]]] if params.direction == "below" else [[vertices[0], config.n + 1]]
        return _candidate_edges(raw)
    if family == "invalid_cycle":
        assert isinstance(params, CycleParameters)
        cycle = vertices[: params.cycle_length]
        return _candidate_edges([*_path(cycle), [cycle[-1], cycle[0]]])
    if family == "invalid_degree3":
        return _candidate_edges([[vertices[0], vertices[index]] for index in range(1, 4)])
    raise AssertionError(f"unreachable generator family: {family}")


def materialize_candidate(config: ExperimentConfig, store: JsonStore) -> InstanceCandidate:
    source = config.source
    if isinstance(source, InlineSource):
        return InstanceCandidate(
            schema_version="1.0.0",
            n=config.n,
            edge_data=cast(list[CandidateJsonValue], source.edges),
            source_metadata=InlineMetadata(kind="inline"),
        )
    if isinstance(source, FileSource):
        value = store.read_json_value(source.path, max_bytes=config.integer_limits.input_max_bytes)
        if not isinstance(value, list):
            raise OperationalError(
                ErrorCode.SCHEMA_INVALID, "Input file must contain a JSON array."
            )
        reference = store.artifact_ref(source.path)
        return InstanceCandidate(
            schema_version="1.0.0",
            n=config.n,
            edge_data=cast(list[CandidateJsonValue], value),
            source_metadata=FileMetadata(
                kind="file",
                path=source.path,
                sha256=reference.sha256,
                size_bytes=reference.size_bytes,
            ),
        )
    assert isinstance(source, GeneratorSource)
    return InstanceCandidate(
        schema_version="1.0.0",
        n=config.n,
        edge_data=generate_edges(config, source),
        source_metadata=GeneratorMetadata(
            kind="generator",
            family=source.family,
            generator_version=source.generator_version,
            seed=source.seed,
            parameters=source.parameters,
        ),
    )
