from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from tesis_domain_extensions.contracts.common import MeasureDefinition
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.reports import ReportSummary


@dataclass(frozen=True)
class DomainProjection:
    context: BaseModel
    core_config: ExperimentConfig | None = None


@dataclass(frozen=True)
class ProjectedCase:
    case_id: str
    core_experiment_id: str
    core_config: ExperimentConfig
    origin: BaseModel
    payload: BaseModel
    linear_forest_edge_component_count: int | None = None
    linear_forest_edge_count: int | None = None


@dataclass
class CaseGenerationStatistics:
    theoretical_combinations: int = 0
    cycle_pruned_branches: int = 0
    degree_pruned_branches: int = 0
    valid_selections: int = 0
    invalid_combinations: int = 0
    forbidden_combinations: int = 0


@dataclass(frozen=True)
class CaseGeneration:
    cases: Iterator[ProjectedCase]
    statistics: CaseGenerationStatistics


class GroupedExecutionProgressObserver(Protocol):
    """Best-effort presentation callbacks for a grouped domain execution."""

    def generation_started(self, total: int) -> None: ...

    def generation_progress(
        self, completed: int, total: int, valid_selections: int | None = None
    ) -> None: ...

    def core_case_started(
        self,
        ordinal: int,
        description: str,
        core_run_id: str | None = None,
        design_id: str | None = None,
    ) -> None: ...


class NullGroupedExecutionProgressObserver:
    """Default observer that keeps application use independent from a terminal."""

    def generation_started(self, total: int) -> None:
        del total

    def generation_progress(
        self, completed: int, total: int, valid_selections: int | None = None
    ) -> None:
        del completed, total, valid_selections

    def core_case_started(
        self,
        ordinal: int,
        description: str,
        core_run_id: str | None = None,
        design_id: str | None = None,
    ) -> None:
        del ordinal, description, core_run_id, design_id


class DomainAdapter(Protocol):
    domain_id: str
    version: str
    description: str
    primary_measure: MeasureDefinition
    grouped_execution: bool
    projection_model: type[BaseModel]
    result_model: type[BaseModel]
    schema_models: dict[str, type[BaseModel]]
    domain_run_model: type[BaseModel] | None
    experiment_summary_model: type[BaseModel]
    run_summary_model: type[BaseModel]

    def decision_criteria(self) -> tuple[BaseModel, ...]: ...

    def parse_config(self, payload: bytes) -> BaseModel: ...

    def project(self, config: Any) -> DomainProjection: ...

    def display_name(self, config: Any) -> str: ...

    def build_projection_record(
        self,
        *,
        domain_experiment_id: str,
        created_at: str,
        config: Any,
        context: Any,
        instance_nonce: str | None,
    ) -> BaseModel: ...

    def parse_projection_record(self, payload: bytes) -> BaseModel: ...

    def iter_cases(self, config: Any, context: Any) -> Iterator[ProjectedCase]: ...

    def generate_cases(
        self,
        config: Any,
        context: Any,
        *,
        on_progress: Callable[[int], None] | None = None,
        is_cancel_requested: Callable[[], bool] | None = None,
    ) -> CaseGeneration: ...

    def theoretical_combinations(self, config: Any) -> int: ...

    def format_case_progress(self, config: Any, case: ProjectedCase) -> str: ...

    def persisted_case_id(self, case: Any) -> str: ...

    def generation_duplicate_count(self, manifest: Any) -> int: ...

    def build_persisted_case(
        self,
        case: ProjectedCase,
        *,
        core_run_id: str,
    ) -> BaseModel: ...

    def build_generation_metrics(
        self,
        config: Any,
        statistics: CaseGenerationStatistics,
        *,
        duplicate_cases: int,
        core_cases: int,
    ) -> BaseModel: ...

    def interpret(
        self,
        report: ReportSummary,
        config: Any,
        context: Any,
        *,
        run_id: str,
        domain_experiment_id: str,
        case: ProjectedCase | None = None,
    ) -> BaseModel: ...

    def build_grouped_result(
        self,
        config: Any,
        context: Any,
        manifest: Any,
        case_results: list[BaseModel],
    ) -> BaseModel: ...

    def render_human(self, result: Any) -> str: ...

    def render_json(self, result: Any) -> bytes: ...

    def render_markdown(self, result: Any) -> str: ...
