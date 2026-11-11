from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, ClassVar, cast

from pydantic import BaseModel, ValidationError

from tesis_domain_extensions.adapters import CaseGeneration, DomainProjection, ProjectedCase
from tesis_domain_extensions.contracts.common import large_non_negative_integer
from tesis_domain_extensions.contracts.projection import domain_experiment_id
from tesis_domain_extensions.domains.single_row_facility_layout.analysis_v2 import (
    build_result_v2,
)
from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
    LayoutCaseOrigin,
    LayoutCasePayload,
    LayoutForestResult,
)
from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
    DomainRunManifestV2,
    SingleRowExperimentProjectionV2,
    SingleRowExperimentSummaryV2,
    SingleRowFacilityLayoutConfigV2,
    SingleRowFacilityLayoutResultV2,
    SingleRowProjectionContextV2,
    SingleRowRunSummaryV2,
    StationVertexV2,
)
from tesis_domain_extensions.domains.single_row_facility_layout.interpretation import (
    PRIMARY_MEASURE,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.catalog import (
    OBJECTIVE_CATALOG,
    selected_objective_snapshots,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.contracts import (
    ObjectiveDefinition,
)
from tesis_domain_extensions.domains.single_row_facility_layout.progress import (
    format_layout_case_progress,
)
from tesis_domain_extensions.errors import DomainExtensionError, invalid_domain_config
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.reports import ReportSummary


class SingleRowFacilityLayoutAdapterV2:
    domain_id = "single-row-facility-layout"
    version = "2.0.0"
    primary_measure = PRIMARY_MEASURE
    description = "Criterios de decisión multidimensionales para disposiciones lineales"
    grouped_execution = True
    projection_model = SingleRowExperimentProjectionV2
    result_model = SingleRowFacilityLayoutResultV2
    domain_run_model = DomainRunManifestV2
    experiment_summary_model = SingleRowExperimentSummaryV2
    run_summary_model = SingleRowRunSummaryV2
    schema_models: ClassVar[dict[str, type[BaseModel]]] = {
        "domain-experiment-config.schema.json": SingleRowFacilityLayoutConfigV2,
        "domain-experiment-projection.schema.json": SingleRowExperimentProjectionV2,
        "domain-experiment-summary.schema.json": SingleRowExperimentSummaryV2,
        "domain-run-summary.schema.json": SingleRowRunSummaryV2,
        "domain-run-manifest.schema.json": DomainRunManifestV2,
        "single-row-facility-layout-result.schema.json": SingleRowFacilityLayoutResultV2,
    }

    def parse_config(self, payload: bytes) -> SingleRowFacilityLayoutConfigV2:
        if payload.startswith(b"\xef\xbb\xbf"):
            raise DomainExtensionError("La configuración no puede contener UTF-8 BOM.")
        try:
            return SingleRowFacilityLayoutConfigV2.model_validate_json(payload)
        except ValidationError as exc:
            raise invalid_domain_config(exc) from exc

    def project(self, config: SingleRowFacilityLayoutConfigV2) -> DomainProjection:
        context = self._context(config)
        from tesis_domain_extensions.domains.single_row_facility_layout.generation import (
            LinearForestGenerator,
        )

        LinearForestGenerator(cast(Any, config), cast(Any, context)).validate_bases()
        return DomainProjection(context=context)

    def display_name(self, config: SingleRowFacilityLayoutConfigV2) -> str:
        return config.study.title

    def build_projection_record(
        self,
        *,
        domain_experiment_id: str,
        created_at: str,
        config: SingleRowFacilityLayoutConfigV2,
        context: SingleRowProjectionContextV2,
        instance_nonce: str | None,
    ) -> SingleRowExperimentProjectionV2:
        return SingleRowExperimentProjectionV2(
            schema_version="2.0.0",
            domain_experiment_id=domain_experiment_id,
            created_at=created_at,
            instance_nonce=instance_nonce,
            domain_config=config,
            projection_context=context,
            objective_snapshots=selected_objective_snapshots(config.decision_model),
        )

    def parse_projection_record(self, payload: bytes) -> SingleRowExperimentProjectionV2:
        return SingleRowExperimentProjectionV2.model_validate_json(
            payload,
            context={"historical_projection": True},
        )

    def generate_cases(
        self,
        config: SingleRowFacilityLayoutConfigV2,
        context: SingleRowProjectionContextV2,
        *,
        on_progress: Callable[[int], None] | None = None,
        is_cancel_requested: Callable[[], bool] | None = None,
    ) -> CaseGeneration:
        from tesis_domain_extensions.domains.single_row_facility_layout.generation import (
            LinearForestGenerator,
        )

        execution = config.execution.model_dump(mode="json")
        generator = LinearForestGenerator(
            cast(Any, config),
            cast(Any, context),
            on_progress=on_progress,
            is_cancel_requested=is_cancel_requested,
        )

        def cases() -> Iterator[ProjectedCase]:
            for generated in generator:
                core_config = ExperimentConfig.model_validate(
                    {
                        "schema_version": "1.0.0",
                        "n": len(config.study.stations),
                        "source": {
                            "kind": "inline",
                            "edges": [list(edge) for edge in generated.numeric_edges],
                        },
                        "methods": execution["methods"],
                        "integer_limits": execution["integer_limits"],
                        "persistence": execution["persistence"],
                        "counting_convention": execution["counting_convention"],
                    }
                )
                yield ProjectedCase(
                    case_id=generated.forest_id,
                    core_experiment_id=domain_experiment_id(core_config),
                    core_config=core_config,
                    origin=generated.origin,
                    payload=generated.payload,
                    linear_forest_edge_component_count=generated.edge_component_count,
                    linear_forest_edge_count=generated.edge_count,
                )

        return CaseGeneration(cases=cases(), statistics=generator.statistics)

    def iter_cases(
        self, config: SingleRowFacilityLayoutConfigV2, context: SingleRowProjectionContextV2
    ) -> Iterator[ProjectedCase]:
        yield from self.generate_cases(config, context).cases

    def theoretical_combinations(self, config: SingleRowFacilityLayoutConfigV2) -> int:
        return sum(
            1
            << len(
                set(item.id for item in config.study.components) - set(design.base_component_ids)
            )
            for design in config.study.designs
        )

    def format_case_progress(
        self, config: SingleRowFacilityLayoutConfigV2, case: ProjectedCase
    ) -> str:
        origin = cast(LayoutCaseOrigin, case.origin)
        design = next(item for item in config.study.designs if item.id == origin.design_id)
        return format_layout_case_progress(
            design_title=design.title,
            added_component_ids=origin.added_component_ids,
            component_station_ids={item.id: item.station_ids for item in config.study.components},
            station_names={item.id: item.name for item in config.study.stations},
        )

    def persisted_case_id(self, case: Any) -> str:
        return cast(str, case.forest_id)

    def generation_duplicate_count(self, manifest: DomainRunManifestV2) -> int:
        return int(manifest.generation.duplicate_forests)

    def build_persisted_case(self, case: ProjectedCase, *, core_run_id: str) -> Any:
        from tesis_domain_extensions.contracts.common import CoreRunAttempt
        from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
            PersistedCaseV2,
        )

        return PersistedCaseV2(
            forest_id=case.case_id,
            core_experiment_id=case.core_experiment_id,
            origins=[cast(LayoutCaseOrigin, case.origin)],
            payload=cast(LayoutCasePayload, case.payload),
            attempts=[CoreRunAttempt(core_run_id=core_run_id, status="created")],
        )

    def build_generation_metrics(
        self,
        config: SingleRowFacilityLayoutConfigV2,
        statistics: Any,
        *,
        duplicate_cases: int,
        core_cases: int,
    ) -> Any:
        from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
            GenerationMetricsV2,
        )

        forbidden = statistics.forbidden_combinations
        return GenerationMetricsV2(
            theoretical_combinations=large_non_negative_integer(
                self.theoretical_combinations(config)
            ),
            cycle_pruned_branches=large_non_negative_integer(statistics.cycle_pruned_branches),
            degree_pruned_branches=large_non_negative_integer(statistics.degree_pruned_branches),
            valid_selections=large_non_negative_integer(statistics.valid_selections),
            invalid_combinations=large_non_negative_integer(statistics.invalid_combinations),
            structural_invalid_combinations=large_non_negative_integer(
                statistics.invalid_combinations - forbidden
            ),
            forbidden_combinations=large_non_negative_integer(forbidden),
            duplicate_forests=large_non_negative_integer(duplicate_cases),
            core_cases=large_non_negative_integer(core_cases),
        )

    def interpret(
        self,
        report: ReportSummary,
        config: SingleRowFacilityLayoutConfigV2,
        context: SingleRowProjectionContextV2,
        *,
        run_id: str,
        domain_experiment_id: str,
        case: ProjectedCase | None = None,
    ) -> LayoutForestResult:
        if case is None:
            raise DomainExtensionError("La interpretación requiere el caso generado.")
        from tesis_domain_extensions.domains.single_row_facility_layout.interpretation import (
            interpret_case,
        )

        return interpret_case(
            report,
            cast(Any, config),
            cast(Any, context),
            case,
            run_id=run_id,
            core_experiment_id=domain_experiment_id,
        )

    def build_grouped_result(
        self,
        config: SingleRowFacilityLayoutConfigV2,
        context: SingleRowProjectionContextV2,
        manifest: Any,
        case_results: list[BaseModel],
    ) -> SingleRowFacilityLayoutResultV2:
        validated = [
            item
            if isinstance(item, LayoutForestResult)
            else LayoutForestResult.model_validate(item)
            for item in case_results
        ]
        return build_result_v2(config, context, manifest, validated)

    def render_human(self, result: SingleRowFacilityLayoutResultV2) -> str:
        cases = sum(len(item.cases) for item in result.designs)
        return f"{result.study_title}: {cases} casos; {len(result.objective_snapshots)} criterios"

    def render_json(self, result: SingleRowFacilityLayoutResultV2) -> bytes:
        return result.model_dump_json(indent=2).encode("utf-8")

    def render_markdown(self, result: SingleRowFacilityLayoutResultV2) -> str:
        return "\n".join(
            [
                f"# {result.study_title}",
                "",
                "## Criterios",
                *[f"- {item.definition.name}" for item in result.objective_snapshots],
            ]
        )

    @staticmethod
    def _context(config: SingleRowFacilityLayoutConfigV2) -> SingleRowProjectionContextV2:
        return SingleRowProjectionContextV2(
            schema_version="2.0.0",
            vertex_mapping=[
                StationVertexV2(vertex=index, station_id=item.id)
                for index, item in enumerate(config.study.stations, start=1)
            ],
        )

    def decision_criteria(self) -> tuple[ObjectiveDefinition, ...]:
        return OBJECTIVE_CATALOG
