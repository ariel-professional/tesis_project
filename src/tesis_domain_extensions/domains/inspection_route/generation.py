from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Literal

from tesis_domain_extensions.adapters import CaseGenerationStatistics, ProjectedCase
from tesis_domain_extensions.contracts.projection import domain_experiment_id
from tesis_domain_extensions.domains.inspection_route.contracts import (
    InspectionConstraintIssue,
    InspectionConstraintPayload,
    InspectionRouteConfig,
    InspectionRouteProjectionContext,
    InspectionScenarioOrigin,
)
from tesis_domain_extensions.errors import DomainRunCancelled
from tesis_domain_extensions.linear_forest import (
    Edge,
    LinearForestConflict,
    linear_forest_id,
    validate_linear_forest,
)
from tesis_proyect.models.config import ExperimentConfig


@dataclass(frozen=True)
class InvalidInspectionScenario:
    scenario_id: str
    constraint_set_id: str
    issue: InspectionConstraintIssue


class InspectionScenarioGenerator:
    def __init__(
        self,
        config: InspectionRouteConfig,
        context: InspectionRouteProjectionContext,
        *,
        on_progress: Callable[[int], None] | None = None,
        is_cancel_requested: Callable[[], bool] | None = None,
    ) -> None:
        self.config = config
        self.vertices = {item.location_id: item.vertex for item in context.vertex_mapping}
        self.location_ids = {item.vertex: item.location_id for item in context.vertex_mapping}
        self.on_progress = on_progress
        self.is_cancel_requested = is_cancel_requested or (lambda: False)
        self.statistics = CaseGenerationStatistics(
            theoretical_combinations=len(config.study.scenarios)
        )
        self.invalid_scenarios: list[InvalidInspectionScenario] = []

    def __iter__(self) -> Iterator[ProjectedCase]:
        self.statistics.valid_selections = 0
        self.statistics.invalid_combinations = 0
        self.statistics.cycle_pruned_branches = 0
        self.statistics.degree_pruned_branches = 0
        self.invalid_scenarios.clear()
        execution = self.config.execution.model_dump(mode="json")
        for completed, scenario in enumerate(self.config.study.scenarios, start=1):
            if self.is_cancel_requested():
                raise DomainRunCancelled
            numeric_edges = self._numeric_edges(scenario.required_consecutive_visits)
            constraint_set_id = linear_forest_id(len(self.vertices), numeric_edges)
            conflict = validate_linear_forest(len(self.vertices), numeric_edges)
            if conflict is not None:
                self.statistics.invalid_combinations += 1
                if conflict.reason == "cycle":
                    self.statistics.cycle_pruned_branches += 1
                else:
                    self.statistics.degree_pruned_branches += 1
                self.invalid_scenarios.append(
                    InvalidInspectionScenario(
                        scenario_id=scenario.id,
                        constraint_set_id=constraint_set_id,
                        issue=self._issue(conflict),
                    )
                )
                self._notify(completed)
                continue
            self.statistics.valid_selections += 1
            core_config = ExperimentConfig.model_validate(
                {
                    "schema_version": "1.0.0",
                    "n": len(self.vertices),
                    "source": {
                        "kind": "inline",
                        "edges": [list(edge) for edge in numeric_edges],
                    },
                    "methods": execution["methods"],
                    "integer_limits": execution["integer_limits"],
                    "persistence": execution["persistence"],
                    "counting_convention": execution["counting_convention"],
                }
            )
            self._notify(completed)
            yield ProjectedCase(
                case_id=constraint_set_id,
                core_experiment_id=domain_experiment_id(core_config),
                core_config=core_config,
                origin=InspectionScenarioOrigin(scenario_id=scenario.id),
                payload=InspectionConstraintPayload(
                    required_consecutive_visits=scenario.required_consecutive_visits
                ),
            )

    def _numeric_edges(self, visits: list[tuple[str, str]]) -> tuple[Edge, ...]:
        return tuple(
            sorted(
                (
                    min(self.vertices[first], self.vertices[second]),
                    max(self.vertices[first], self.vertices[second]),
                )
                for first, second in visits
            )
        )

    def _issue(self, conflict: LinearForestConflict) -> InspectionConstraintIssue:
        reason: Literal["cycle", "degree_exceeded"] = conflict.reason
        if reason == "cycle":
            message = (
                "Las obligaciones forman un circuito cerrado y no pueden integrarse en "
                "un recorrido lineal."
            )
        else:
            message = (
                "Una instalación debería ser consecutiva a más de dos instalaciones, "
                "algo imposible en un recorrido lineal."
            )
        return InspectionConstraintIssue(
            reason=reason,
            message=message,
            affected_location_ids=[
                self.location_ids[vertex] for vertex in conflict.affected_vertices
            ],
            conflicting_consecutive_visits=[
                (self.location_ids[first], self.location_ids[second])
                for first, second in conflict.edges
            ],
        )

    def _notify(self, completed: int) -> None:
        if self.on_progress is not None:
            self.on_progress(completed)
