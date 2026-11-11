from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from tesis_proyect.models.common import Diagnostic, Edge
from tesis_proyect.models.enums import DOMAIN_ERROR_CODES, ErrorCode
from tesis_proyect.models.scientific import ValidationResult

_PRECEDENCE = {
    ErrorCode.MALFORMED_EDGE: 1,
    ErrorCode.LOOP_EDGE: 2,
    ErrorCode.DUPLICATE_EDGE: 3,
    ErrorCode.VERTEX_OUT_OF_RANGE: 4,
    ErrorCode.CYCLE_DETECTED: 5,
    ErrorCode.MAX_DEGREE_EXCEEDED: 6,
}


@dataclass(frozen=True)
class EdgeValidation:
    result: ValidationResult
    edges: tuple[Edge, ...] | None


def _diagnostic(code: ErrorCode, message: str, index: int | None, edge: Any) -> Diagnostic:
    return Diagnostic(
        code=code,
        domain_error_code=DOMAIN_ERROR_CODES[code],
        message=message,
        edge_index=index,
        edge=edge,
    )


def _sort_diagnostics(items: list[Diagnostic]) -> list[Diagnostic]:
    return sorted(
        items,
        key=lambda item: (
            _PRECEDENCE[item.code],
            item.edge_index if item.edge_index is not None else -1,
            json.dumps(item.edge, ensure_ascii=False, sort_keys=True, default=str),
        ),
    )


def validate_edges(n: int, edge_data: list[Any]) -> EdgeValidation:
    errors: list[Diagnostic] = []
    normalized: list[Edge] = []
    first_seen: dict[Edge, int] = {}
    for index, raw in enumerate(edge_data):
        if (
            not isinstance(raw, list)
            or len(raw) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) for item in raw)
        ):
            errors.append(
                _diagnostic(ErrorCode.MALFORMED_EDGE, "Edge must contain two integers.", index, raw)
            )
            continue
        u, v = raw
        edge = (min(u, v), max(u, v))
        if u == v:
            errors.append(
                _diagnostic(ErrorCode.LOOP_EDGE, "Loop edges are not allowed.", index, raw)
            )
        if not 1 <= u <= n or not 1 <= v <= n:
            errors.append(
                _diagnostic(
                    ErrorCode.VERTEX_OUT_OF_RANGE,
                    f"Edge endpoints must be between 1 and {n}.",
                    index,
                    raw,
                )
            )
        if edge in first_seen:
            errors.append(
                _diagnostic(
                    ErrorCode.DUPLICATE_EDGE,
                    f"Undirected edge duplicates edge at index {first_seen[edge]}.",
                    index,
                    raw,
                )
            )
        else:
            first_seen[edge] = index
        normalized.append(edge)
    errors = _sort_diagnostics(errors)
    result = ValidationResult(schema_version="1.0.0", valid=not errors, errors=errors, warnings=[])
    return EdgeValidation(result=result, edges=tuple(sorted(normalized)) if not errors else None)


def validate_linear_forest(n: int, edges: tuple[Edge, ...]) -> ValidationResult:
    adjacency: list[list[int]] = [[] for _ in range(n + 1)]
    errors: list[Diagnostic] = []
    for u, v in edges:
        adjacency[u].append(v)
        adjacency[v].append(u)
    for vertex in range(1, n + 1):
        if len(adjacency[vertex]) > 2:
            errors.append(
                _diagnostic(
                    ErrorCode.MAX_DEGREE_EXCEEDED,
                    f"Vertex {vertex} has degree {len(adjacency[vertex])}.",
                    None,
                    None,
                )
            )
    visited: set[int] = set()

    def visit(vertex: int, parent: int) -> bool:
        visited.add(vertex)
        for neighbor in adjacency[vertex]:
            if neighbor == parent:
                continue
            if neighbor in visited or visit(neighbor, vertex):
                return True
        return False

    if any(
        vertex not in visited and adjacency[vertex] and visit(vertex, 0)
        for vertex in range(1, n + 1)
    ):
        errors.append(
            _diagnostic(
                ErrorCode.CYCLE_DETECTED, "The prescribed edges contain a cycle.", None, None
            )
        )
    return ValidationResult(
        schema_version="1.0.0",
        valid=not errors,
        errors=_sort_diagnostics(errors),
        warnings=[],
    )
