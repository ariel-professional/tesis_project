from __future__ import annotations

from typing import Literal

from tesis_proyect.models.common import Edge
from tesis_proyect.models.scientific import LinearForestAnalysis, PathComponent

CaseType = Literal[
    "empty",
    "hamiltonian_path_extreme",
    "single_edge",
    "matching",
    "single_path",
    "multiple_paths",
]


def _classify(n: int, lengths: list[int], free: list[int]) -> CaseType:
    if not lengths:
        return "empty"
    if len(lengths) == 1 and not free and lengths[0] == n - 1:
        return "hamiltonian_path_extreme"
    if len(lengths) == 1 and lengths[0] == 1:
        return "single_edge"
    if len(lengths) >= 2 and all(length == 1 for length in lengths):
        return "matching"
    if len(lengths) == 1:
        return "single_path"
    return "multiple_paths"


def analyze_linear_forest(n: int, edges: tuple[Edge, ...]) -> LinearForestAnalysis:
    adjacency: dict[int, list[int]] = {vertex: [] for vertex in range(1, n + 1)}
    for u, v in edges:
        adjacency[u].append(v)
        adjacency[v].append(u)
    components: list[PathComponent] = []
    used: set[int] = set()
    endpoints = sorted(vertex for vertex, neighbors in adjacency.items() if len(neighbors) == 1)
    for start in endpoints:
        if start in used:
            continue
        path = [start]
        previous = 0
        current = start
        while True:
            used.add(current)
            next_vertices = [value for value in adjacency[current] if value != previous]
            if not next_vertices:
                break
            previous, current = current, next_vertices[0]
            path.append(current)
        reverse = list(reversed(path))
        vertices = min(path, reverse)
        component_edges = [
            (min(vertices[i], vertices[i + 1]), max(vertices[i], vertices[i + 1]))
            for i in range(len(vertices) - 1)
        ]
        components.append(
            PathComponent(
                vertices=vertices, edges=component_edges, edge_length=len(component_edges)
            )
        )
    components.sort(key=lambda component: component.vertices)
    free = sorted(vertex for vertex in range(1, n + 1) if not adjacency[vertex])
    lengths = [component.edge_length for component in components]
    case_type = _classify(n, lengths, free)
    return LinearForestAnalysis(
        schema_version="1.0.0",
        components=components,
        component_lengths=lengths,
        free_vertices=free,
        free_vertex_count=len(free),
        blocks=len(components) + len(free),
        case_type=case_type,
    )


def validate_analysis_integrity(
    n: int,
    edges: tuple[Edge, ...],
    analysis: LinearForestAnalysis,
) -> bool:
    """Validate persisted mathematical structure against its canonical derivation."""
    return analysis == analyze_linear_forest(n, edges)
