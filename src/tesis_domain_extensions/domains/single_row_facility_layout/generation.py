from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from itertools import combinations
from typing import Literal, cast

from tesis_domain_extensions.adapters import CaseGenerationStatistics
from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
    LayoutCaseOrigin,
    LayoutCasePayload,
    LayoutDesign,
    LinearComponent,
    SingleRowFacilityLayoutConfig,
    SingleRowProjectionContext,
)
from tesis_domain_extensions.errors import DomainExtensionError, DomainRunCancelled
from tesis_domain_extensions.linear_forest import (
    Edge,
    LinearForestConflict,
    RollbackLinearForest,
    linear_forest_id,
)

StationEdge = tuple[str, str]


@dataclass(frozen=True)
class GeneratedForest:
    forest_id: str
    origin: LayoutCaseOrigin
    payload: LayoutCasePayload
    numeric_edges: tuple[Edge, ...]
    edge_component_count: int
    edge_count: int


@dataclass(frozen=True)
class GeneratedInvalidCombination:
    design_id: str
    added_component_ids: tuple[str, ...]
    reason: Literal["cycle", "degree_exceeded", "forbidden"]
    affected_station_ids: tuple[str, ...]
    conflicting_edges: tuple[StationEdge, ...]
    conflicting_component_ids: tuple[str, ...]


@dataclass(frozen=True)
class GeneratedConflictSummary:
    design_id: str
    reason: Literal["cycle", "degree_exceeded", "forbidden"]
    affected_station_ids: tuple[str, ...]
    conflicting_edges: tuple[StationEdge, ...]
    conflicting_component_ids: tuple[str, ...]
    combination_count: int


def _component_edges(
    component: LinearComponent,
    vertices: Mapping[str, int],
) -> tuple[Edge, ...]:
    return tuple(
        sorted(
            {
                (min(vertices[first], vertices[second]), max(vertices[first], vertices[second]))
                for first, second in zip(
                    component.station_ids,
                    component.station_ids[1:],
                    strict=False,
                )
            }
        )
    )


forest_id = linear_forest_id


class LinearForestGenerator:
    def __init__(
        self,
        config: SingleRowFacilityLayoutConfig,
        context: SingleRowProjectionContext,
        *,
        on_progress: Callable[[int], None] | None = None,
        is_cancel_requested: Callable[[], bool] | None = None,
        collect_invalid_details: bool = True,
    ) -> None:
        self.config = config
        self.vertices = {item.station_id: item.vertex for item in context.vertex_mapping}
        self.station_ids = {item.vertex: item.station_id for item in context.vertex_mapping}
        self.components = {component.id: component for component in config.study.components}
        self.component_edges = {
            identifier: _component_edges(component, self.vertices)
            for identifier, component in self.components.items()
        }
        self.statistics = CaseGenerationStatistics()
        self.on_progress = on_progress
        self.is_cancel_requested = is_cancel_requested or (lambda: False)
        self.collect_invalid_details = collect_invalid_details
        self.invalid_combinations: list[GeneratedInvalidCombination] = []
        self._conflict_counts: dict[
            tuple[
                str,
                Literal["cycle", "degree_exceeded", "forbidden"],
                tuple[str, ...],
                tuple[StationEdge, ...],
                tuple[str, ...],
            ],
            int,
        ] = {}
        decision_model = getattr(config, "decision_model", None)
        undesired = getattr(decision_model, "undesired_prescribed_adjacencies", ())
        self.forbidden_edges = {
            tuple(sorted((item.first_station_id, item.second_station_id)))
            for item in undesired
            if item.policy == "forbidden"
        }

    def validate_bases(self) -> None:
        for design in self.config.study.designs:
            state = RollbackLinearForest(len(self.vertices))
            base_edges: set[StationEdge] = set()
            for component_id in design.base_component_ids:
                conflict = state.add_edges(self.component_edges[component_id])
                if conflict is not None:
                    raise DomainExtensionError(
                        f"El diseño '{design.id}' tiene una base inválida ({conflict.reason}).",
                        exit_code=65,
                    )
                base_edges.update(self._edges_to_station_ids(self.component_edges[component_id]))
            forbidden = base_edges.intersection(self.forbidden_edges)
            if forbidden:
                raise DomainExtensionError(
                    f"El diseño '{design.id}' prescribe una adyacencia prohibida: "
                    f"{sorted(forbidden)[0]}.",
                    exit_code=65,
                )

    def __iter__(self) -> Iterator[GeneratedForest]:
        self.statistics.theoretical_combinations = 0
        self.statistics.cycle_pruned_branches = 0
        self.statistics.degree_pruned_branches = 0
        self.statistics.valid_selections = 0
        self.statistics.invalid_combinations = 0
        self.statistics.forbidden_combinations = 0
        self.invalid_combinations.clear()
        self._conflict_counts.clear()
        for design in self.config.study.designs:
            variables = [
                identifier
                for identifier in self.components
                if identifier not in design.base_component_ids
            ]
            variables.sort(key=lambda item: (-len(self.component_edges[item]), item))
            self.statistics.theoretical_combinations += 1 << len(variables)
            state = RollbackLinearForest(len(self.vertices))
            for component_id in design.base_component_ids:
                conflict = state.add_edges(self.component_edges[component_id])
                if conflict is not None:
                    raise DomainExtensionError(
                        f"El diseño '{design.id}' tiene una base inválida ({conflict.reason}).",
                        exit_code=65,
                    )
            yield from self._visit(design, variables, 0, [], state)

    def _visit(
        self,
        design: LayoutDesign,
        variables: list[str],
        index: int,
        selected: list[str],
        state: RollbackLinearForest,
    ) -> Iterator[GeneratedForest]:
        if self.is_cancel_requested():
            raise DomainRunCancelled
        if index == len(variables):
            self.statistics.valid_selections += 1
            self._notify_progress()
            numeric_edges = tuple(sorted(state.edges))
            component_ids = [*design.base_component_ids, *selected]
            station_edges = [
                (self.station_ids[first], self.station_ids[second])
                for first, second in numeric_edges
            ]
            yield GeneratedForest(
                forest_id=forest_id(len(self.vertices), numeric_edges),
                origin=LayoutCaseOrigin(
                    design_id=design.id,
                    added_component_ids=sorted(selected),
                ),
                payload=LayoutCasePayload(
                    component_ids=component_ids,
                    edges=station_edges,
                ),
                numeric_edges=numeric_edges,
                edge_component_count=len(
                    {state.find(vertex) for edge in numeric_edges for vertex in edge}
                ),
                edge_count=len(numeric_edges),
            )
            return
        component_id = variables[index]
        yield from self._visit(design, variables, index + 1, selected, state)
        checkpoint = state.checkpoint()
        conflict = state.add_edges(self.component_edges[component_id])
        component_station_edges: set[tuple[str, str]] = {
            cast(
                tuple[str, str],
                tuple(sorted((self.station_ids[first], self.station_ids[second]))),
            )
            for first, second in self.component_edges[component_id]
        }
        forbidden = component_station_edges.intersection(self.forbidden_edges)
        if conflict is None and not forbidden:
            selected.append(component_id)
            yield from self._visit(design, variables, index + 1, selected, state)
            selected.pop()
        else:
            if forbidden:
                self._record_forbidden_branch(
                    design, variables, index, selected, component_id, forbidden
                )
            elif conflict is not None and conflict.reason == "cycle":
                self.statistics.cycle_pruned_branches += 1
            else:
                self.statistics.degree_pruned_branches += 1
            if conflict is not None and not forbidden:
                self._record_invalid_branch(
                    design, variables, index, selected, component_id, conflict
                )
            self._notify_progress()
        state.rollback(checkpoint)

    def _notify_progress(self) -> None:
        if self.on_progress is not None:
            self.on_progress(
                self.statistics.valid_selections + self.statistics.invalid_combinations
            )

    def conflict_summaries(self) -> list[GeneratedConflictSummary]:
        return [
            GeneratedConflictSummary(
                design_id=key[0],
                reason=key[1],
                affected_station_ids=key[2],
                conflicting_edges=key[3],
                conflicting_component_ids=key[4],
                combination_count=count,
            )
            for key, count in sorted(self._conflict_counts.items())
        ]

    def _edges_to_station_ids(self, edges: tuple[Edge, ...]) -> tuple[StationEdge, ...]:
        return tuple((self.station_ids[first], self.station_ids[second]) for first, second in edges)

    def _record_invalid_branch(
        self,
        design: LayoutDesign,
        variables: list[str],
        index: int,
        selected: list[str],
        component_id: str,
        conflict: LinearForestConflict,
    ) -> None:
        remaining = variables[index + 1 :]
        combination_count = 1 << len(remaining)
        self.statistics.invalid_combinations += combination_count
        affected = tuple(self.station_ids[vertex] for vertex in conflict.affected_vertices)
        conflict_edges = tuple(
            (self.station_ids[first], self.station_ids[second]) for first, second in conflict.edges
        )
        included = [*design.base_component_ids, *selected, component_id]
        conflict_edge_set = set(conflict.edges)
        conflict_components = tuple(
            sorted(
                identifier
                for identifier in included
                if conflict_edge_set.intersection(self.component_edges[identifier])
            )
        )
        key = (design.id, conflict.reason, affected, conflict_edges, conflict_components)
        self._conflict_counts[key] = self._conflict_counts.get(key, 0) + combination_count
        reporting = getattr(self.config.reporting, "invalid_combinations", self.config.reporting)
        if reporting != "full" or not self.collect_invalid_details:
            return
        for size in range(len(remaining) + 1):
            for suffix in combinations(remaining, size):
                self.invalid_combinations.append(
                    GeneratedInvalidCombination(
                        design_id=design.id,
                        added_component_ids=tuple(sorted([*selected, component_id, *suffix])),
                        reason=conflict.reason,
                        affected_station_ids=affected,
                        conflicting_edges=conflict_edges,
                        conflicting_component_ids=conflict_components,
                    )
                )

    def _record_forbidden_branch(
        self,
        design: LayoutDesign,
        variables: list[str],
        index: int,
        selected: list[str],
        component_id: str,
        forbidden: set[tuple[str, str]],
    ) -> None:
        remaining = variables[index + 1 :]
        combination_count = 1 << len(remaining)
        self.statistics.invalid_combinations += combination_count
        self.statistics.forbidden_combinations += combination_count
        conflict_edges = tuple(sorted(forbidden))
        affected = tuple(sorted({station for edge in conflict_edges for station in edge}))
        included = tuple(sorted([*design.base_component_ids, *selected, component_id]))
        reason: Literal["cycle", "degree_exceeded", "forbidden"] = "forbidden"
        key = (design.id, reason, affected, conflict_edges, included)
        self._conflict_counts[key] = self._conflict_counts.get(key, 0) + combination_count
        reporting = getattr(self.config.reporting, "invalid_combinations", self.config.reporting)
        if reporting != "full" or not self.collect_invalid_details:
            return
        for size in range(len(remaining) + 1):
            for suffix in combinations(remaining, size):
                self.invalid_combinations.append(
                    GeneratedInvalidCombination(
                        design_id=design.id,
                        added_component_ids=tuple(sorted([*selected, component_id, *suffix])),
                        reason="forbidden",
                        affected_station_ids=affected,
                        conflicting_edges=conflict_edges,
                        conflicting_component_ids=included,
                    )
                )
