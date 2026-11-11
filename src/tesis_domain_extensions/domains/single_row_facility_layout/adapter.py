from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import ClassVar, cast

from pydantic import BaseModel, ValidationError

from tesis_domain_extensions.adapters import (
    CaseGeneration,
    CaseGenerationStatistics,
    DomainProjection,
    ProjectedCase,
)
from tesis_domain_extensions.contracts.common import CoreRunAttempt, large_non_negative_integer
from tesis_domain_extensions.contracts.projection import domain_experiment_id
from tesis_domain_extensions.domains.single_row_facility_layout.analysis import build_result
from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
    DomainRunManifest,
    GenerationMetrics,
    LayoutCaseOrigin,
    LayoutCasePayload,
    LayoutForestResult,
    PersistedCase,
    SingleRowExperimentProjection,
    SingleRowExperimentSummary,
    SingleRowFacilityLayoutConfig,
    SingleRowFacilityLayoutResult,
    SingleRowProjectionContext,
    SingleRowRunSummary,
    StationVertex,
)
from tesis_domain_extensions.domains.single_row_facility_layout.generation import (
    LinearForestGenerator,
)
from tesis_domain_extensions.domains.single_row_facility_layout.interpretation import (
    PRIMARY_MEASURE,
    interpret_case,
)
from tesis_domain_extensions.domains.single_row_facility_layout.progress import (
    format_layout_case_progress,
)
from tesis_domain_extensions.domains.single_row_facility_layout.render import (
    render_human,
    render_json,
    render_markdown,
)
from tesis_domain_extensions.errors import DomainExtensionError, invalid_domain_config
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.reports import ReportSummary


class SingleRowFacilityLayoutAdapter:
    domain_id = "single-row-facility-layout"
    version = "1.0.0"
    description = "Flexibilidad de disposiciones de estaciones en una sola fila"
    grouped_execution = True
    projection_model = SingleRowExperimentProjection
    result_model = SingleRowFacilityLayoutResult
    domain_run_model = DomainRunManifest
    experiment_summary_model = SingleRowExperimentSummary
    run_summary_model = SingleRowRunSummary
    primary_measure = PRIMARY_MEASURE
    schema_models: ClassVar[dict[str, type[BaseModel]]] = {
        "domain-experiment-config.schema.json": SingleRowFacilityLayoutConfig,
        "domain-experiment-projection.schema.json": SingleRowExperimentProjection,
        "domain-experiment-summary.schema.json": SingleRowExperimentSummary,
        "domain-run-summary.schema.json": SingleRowRunSummary,
        "domain-run-manifest.schema.json": DomainRunManifest,
        "single-row-facility-layout-result.schema.json": SingleRowFacilityLayoutResult,
    }

    def parse_config(self, payload: bytes) -> SingleRowFacilityLayoutConfig:
        if payload.startswith(b"\xef\xbb\xbf"):
            raise DomainExtensionError("La configuración no puede contener UTF-8 BOM.")
        try:
            config = SingleRowFacilityLayoutConfig.model_validate_json(payload)
        except ValidationError as exc:
            raise invalid_domain_config(exc) from exc
        except (UnicodeDecodeError, ValueError) as exc:
            raise DomainExtensionError("La configuración del dominio es inválida.") from exc
        context = self._context(config)
        LinearForestGenerator(config, context).validate_bases()
        return config

    def project(self, config: SingleRowFacilityLayoutConfig) -> DomainProjection:
        context = self._context(config)
        LinearForestGenerator(config, context).validate_bases()
        return DomainProjection(context=context)

    def display_name(self, config: SingleRowFacilityLayoutConfig) -> str:
        return config.study.title

    def build_projection_record(
        self,
        *,
        domain_experiment_id: str,
        created_at: str,
        config: SingleRowFacilityLayoutConfig,
        context: SingleRowProjectionContext,
        instance_nonce: str | None,
    ) -> SingleRowExperimentProjection:
        return SingleRowExperimentProjection(
            schema_version="1.0.0",
            domain_experiment_id=domain_experiment_id,
            created_at=created_at,
            instance_nonce=instance_nonce,
            domain_config=config,
            projection_context=context,
        )

    def parse_projection_record(self, payload: bytes) -> SingleRowExperimentProjection:
        return SingleRowExperimentProjection.model_validate_json(payload)

    def iter_cases(
        self,
        config: SingleRowFacilityLayoutConfig,
        context: SingleRowProjectionContext,
    ) -> Iterator[ProjectedCase]:
        yield from self.generate_cases(config, context).cases

    def generate_cases(
        self,
        config: SingleRowFacilityLayoutConfig,
        context: SingleRowProjectionContext,
        *,
        on_progress: Callable[[int], None] | None = None,
        is_cancel_requested: Callable[[], bool] | None = None,
    ) -> CaseGeneration:
        execution = config.execution.model_dump(mode="json")
        generator = LinearForestGenerator(
            config,
            context,
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
                )

        return CaseGeneration(cases=cases(), statistics=generator.statistics)

    def theoretical_combinations(self, config: SingleRowFacilityLayoutConfig) -> int:
        components = {component.id for component in config.study.components}
        return sum(
            1 << len(components.difference(design.base_component_ids))
            for design in config.study.designs
        )

    def format_case_progress(
        self,
        config: SingleRowFacilityLayoutConfig,
        case: ProjectedCase,
    ) -> str:
        origin = cast(LayoutCaseOrigin, case.origin)
        design = next(design for design in config.study.designs if design.id == origin.design_id)
        return format_layout_case_progress(
            design_title=design.title,
            added_component_ids=origin.added_component_ids,
            component_station_ids={item.id: item.station_ids for item in config.study.components},
            station_names={item.id: item.name for item in config.study.stations},
        )

    def persisted_case_id(self, case: PersistedCase) -> str:
        return case.forest_id

    def generation_duplicate_count(self, manifest: DomainRunManifest) -> int:
        return int(manifest.generation.duplicate_forests)

    def build_persisted_case(
        self,
        case: ProjectedCase,
        *,
        core_run_id: str,
    ) -> PersistedCase:
        return PersistedCase(
            forest_id=case.case_id,
            core_experiment_id=case.core_experiment_id,
            origins=[cast(LayoutCaseOrigin, case.origin)],
            payload=cast(LayoutCasePayload, case.payload),
            attempts=[CoreRunAttempt(core_run_id=core_run_id, status="created")],
        )

    def build_generation_metrics(
        self,
        config: SingleRowFacilityLayoutConfig,
        statistics: CaseGenerationStatistics,
        *,
        duplicate_cases: int,
        core_cases: int,
    ) -> GenerationMetrics:
        return GenerationMetrics(
            theoretical_combinations=large_non_negative_integer(
                self.theoretical_combinations(config)
            ),
            cycle_pruned_branches=large_non_negative_integer(statistics.cycle_pruned_branches),
            degree_pruned_branches=large_non_negative_integer(statistics.degree_pruned_branches),
            valid_selections=large_non_negative_integer(statistics.valid_selections),
            invalid_combinations=large_non_negative_integer(statistics.invalid_combinations),
            duplicate_forests=large_non_negative_integer(duplicate_cases),
            core_cases=large_non_negative_integer(core_cases),
        )

    def interpret(
        self,
        report: ReportSummary,
        config: SingleRowFacilityLayoutConfig,
        context: SingleRowProjectionContext,
        *,
        run_id: str,
        domain_experiment_id: str,
        case: ProjectedCase | None = None,
    ) -> LayoutForestResult:
        if case is None:
            raise DomainExtensionError("La interpretación requiere el caso generado.")
        return interpret_case(
            report,
            config,
            context,
            case,
            run_id=run_id,
            core_experiment_id=domain_experiment_id,
        )

    def build_grouped_result(
        self,
        config: SingleRowFacilityLayoutConfig,
        context: SingleRowProjectionContext,
        manifest: object,
        case_results: list[BaseModel],
    ) -> SingleRowFacilityLayoutResult:
        domain_manifest = (
            manifest
            if isinstance(manifest, DomainRunManifest)
            else DomainRunManifest.model_validate(manifest)
        )
        validated = [
            item
            if isinstance(item, LayoutForestResult)
            else LayoutForestResult.model_validate(item)
            for item in case_results
        ]
        return build_result(config, context, domain_manifest, validated)

    def render_human(self, result: SingleRowFacilityLayoutResult) -> str:
        return render_human(result)

    def render_json(self, result: SingleRowFacilityLayoutResult) -> bytes:
        return render_json(result)

    def render_markdown(self, result: SingleRowFacilityLayoutResult) -> str:
        return render_markdown(result)

    @staticmethod
    def _context(config: SingleRowFacilityLayoutConfig) -> SingleRowProjectionContext:
        return SingleRowProjectionContext(
            schema_version="1.0.0",
            vertex_mapping=[
                StationVertex(vertex=index, station_id=station.id)
                for index, station in enumerate(config.study.stations, start=1)
            ],
        )
