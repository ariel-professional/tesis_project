from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

Edge = tuple[int, int]


@dataclass(frozen=True)
class LinearForestConflict:
    reason: Literal["cycle", "degree_exceeded"]
    affected_vertices: tuple[int, ...]
    edges: tuple[Edge, ...]


class RollbackLinearForest:
    """Incremental linear-forest validator shared by domain case generators."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n + 1))
        self.size = [1] * (n + 1)
        self.degree = [0] * (n + 1)
        self.edges: set[Edge] = set()
        self.history: list[tuple[int, int, int, Edge]] = []

    def find(self, vertex: int) -> int:
        while self.parent[vertex] != vertex:
            vertex = self.parent[vertex]
        return vertex

    def checkpoint(self) -> int:
        return len(self.history)

    def add_edges(self, edges: tuple[Edge, ...]) -> LinearForestConflict | None:
        checkpoint = self.checkpoint()
        for edge in edges:
            if edge in self.edges:
                continue
            first, second = edge
            if self.degree[first] >= 2 or self.degree[second] >= 2:
                affected = tuple(vertex for vertex in edge if self.degree[vertex] >= 2)
                incident = {
                    current
                    for current in self.edges
                    if any(vertex in current for vertex in affected)
                }
                conflict = LinearForestConflict(
                    "degree_exceeded",
                    affected,
                    tuple(sorted({edge, *incident})),
                )
                self.rollback(checkpoint)
                return conflict
            first_root = self.find(first)
            second_root = self.find(second)
            if first_root == second_root:
                path_edges = self._path_edges(first, second)
                affected = tuple(sorted({vertex for current in path_edges for vertex in current}))
                conflict = LinearForestConflict(
                    "cycle",
                    affected,
                    tuple(sorted({edge, *path_edges})),
                )
                self.rollback(checkpoint)
                return conflict
            if self.size[first_root] < self.size[second_root]:
                first_root, second_root = second_root, first_root
            old_size = self.size[first_root]
            self.parent[second_root] = first_root
            self.size[first_root] += self.size[second_root]
            self.degree[first] += 1
            self.degree[second] += 1
            self.edges.add(edge)
            self.history.append((second_root, first_root, old_size, edge))
        return None

    def _path_edges(self, start: int, finish: int) -> tuple[Edge, ...]:
        adjacency: dict[int, list[int]] = {}
        for first, second in self.edges:
            adjacency.setdefault(first, []).append(second)
            adjacency.setdefault(second, []).append(first)
        pending: list[tuple[int, int | None, tuple[Edge, ...]]] = [(start, None, ())]
        while pending:
            vertex, previous, path = pending.pop()
            if vertex == finish:
                return path
            for following in sorted(adjacency.get(vertex, []), reverse=True):
                if following == previous:
                    continue
                edge = (min(vertex, following), max(vertex, following))
                pending.append((following, vertex, (*path, edge)))
        raise RuntimeError("connected vertices must have a path")

    def rollback(self, checkpoint: int) -> None:
        while len(self.history) > checkpoint:
            child, parent, old_size, edge = self.history.pop()
            self.parent[child] = child
            self.size[parent] = old_size
            first, second = edge
            self.degree[first] -= 1
            self.degree[second] -= 1
            self.edges.remove(edge)


def validate_linear_forest(n: int, edges: tuple[Edge, ...]) -> LinearForestConflict | None:
    return RollbackLinearForest(n).add_edges(edges)


def linear_forest_id(n: int, edges: tuple[Edge, ...]) -> str:
    payload = json.dumps(
        {"edges": [list(edge) for edge in edges], "n": n},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
