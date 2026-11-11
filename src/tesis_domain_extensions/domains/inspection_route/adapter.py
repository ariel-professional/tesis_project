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
from tesis_domain_extensions.domains.inspection_route.analysis import build_result
from tesis_domain_extensions.domains.inspection_route.contracts import (
    InspectionConstraintPayload,
    InspectionConstraintSetResult,
    InspectionDomainRunManifest,
    InspectionExperimentSummary,
    InspectionGenerationMetrics,
    InspectionRouteConfig,
    InspectionRouteProjection,
    InspectionRouteProjectionContext,
    InspectionRouteResult,
    InspectionRunSummary,
    InspectionScenarioOrigin,
    LocationVertex,
    PersistedConstraintSet,
)
from tesis_domain_extensions.domains.inspection_route.generation import (
    InspectionScenarioGenerator,
)
from tesis_domain_extensions.domains.inspection_route.interpretation import (
    PRIMARY_MEASURE,
    interpret_case,
)
from tesis_domain_extensions.domains.inspection_route.render import (
    render_human,
    render_json,
    render_markdown,
)
from tesis_domain_extensions.errors import DomainExtensionError, invalid_domain_config
from tesis_proyect.models.reports import ReportSummary


class InspectionRouteAdapter:
    domain_id = "inspection-route"
    version = "1.0.0"
    description = "Comparación de políticas de inspección con visitas consecutivas obligatorias"
    grouped_execution = True
    projection_model = InspectionRouteProjection
    result_model = InspectionRouteResult
    domain_run_model = InspectionDomainRunManifest
    experiment_summary_model = InspectionExperimentSummary
    run_summary_model = InspectionRunSummary
    primary_measure = PRIMARY_MEASURE
    schema_models: ClassVar[dict[str, type[BaseModel]]] = {
        "domain-experiment-config.schema.json": InspectionRouteConfig,
        "domain-experiment-projection.schema.json": InspectionRouteProjection,
        "domain-experiment-summary.schema.json": InspectionExperimentSummary,
        "domain-run-summary.schema.json": InspectionRunSummary,
        "domain-run-manifest.schema.json": InspectionDomainRunManifest,
        "inspection-route-result.schema.json": InspectionRouteResult,
    }

    def parse_config(self, payload: bytes) -> InspectionRouteConfig:
        if payload.startswith(b"\xef\xbb\xbf"):
            raise DomainExtensionError("La configuración no puede contener UTF-8 BOM.")
        try:
            return InspectionRouteConfig.model_validate_json(payload)
        except ValidationError as exc:
            raise invalid_domain_config(exc) from exc
        except (UnicodeDecodeError, ValueError) as exc:
            raise DomainExtensionError("La configuración del dominio es inválida.") from exc

    def project(self, config: InspectionRouteConfig) -> DomainProjection:
        return DomainProjection(context=self._context(config))

    def display_name(self, config: InspectionRouteConfig) -> str:
        return config.study.title

    def build_projection_record(
        self,
        *,
        domain_experiment_id: str,
        created_at: str,
        config: InspectionRouteConfig,
        context: InspectionRouteProjectionContext,
        instance_nonce: str | None,
    ) -> InspectionRouteProjection:
        return InspectionRouteProjection(
            schema_version="1.0.0",
            domain_experiment_id=domain_experiment_id,
            created_at=created_at,
            instance_nonce=instance_nonce,
            domain_config=config,
            projection_context=context,
        )

    def parse_projection_record(self, payload: bytes) -> InspectionRouteProjection:
        return InspectionRouteProjection.model_validate_json(payload)

    def iter_cases(
        self,
        config: InspectionRouteConfig,
        context: InspectionRouteProjectionContext,
    ) -> Iterator[ProjectedCase]:
        yield from self.generate_cases(config, context).cases

    def generate_cases(
        self,
        config: InspectionRouteConfig,
        context: InspectionRouteProjectionContext,
        *,
        on_progress: Callable[[int], None] | None = None,
        is_cancel_requested: Callable[[], bool] | None = None,
    ) -> CaseGeneration:
        generator = InspectionScenarioGenerator(
            config,
            context,
            on_progress=on_progress,
            is_cancel_requested=is_cancel_requested,
        )
        return CaseGeneration(cases=iter(generator), statistics=generator.statistics)

    def theoretical_combinations(self, config: InspectionRouteConfig) -> int:
        return len(config.study.scenarios)

    def format_case_progress(
        self,
        config: InspectionRouteConfig,
        case: ProjectedCase,
    ) -> str:
        scenario_id = cast(InspectionScenarioOrigin, case.origin).scenario_id
        scenario = next(item for item in config.study.scenarios if item.id == scenario_id)
        return f"escenario {scenario.id}: {scenario.title}"

    def persisted_case_id(self, case: PersistedConstraintSet) -> str:
        return case.constraint_set_id

    def generation_duplicate_count(self, manifest: InspectionDomainRunManifest) -> int:
        return int(manifest.generation.duplicate_constraint_sets)

    def build_persisted_case(
        self,
        case: ProjectedCase,
        *,
        core_run_id: str,
    ) -> PersistedConstraintSet:
        return PersistedConstraintSet(
            constraint_set_id=case.case_id,
            core_experiment_id=case.core_experiment_id,
            origins=[cast(InspectionScenarioOrigin, case.origin)],
            payload=cast(InspectionConstraintPayload, case.payload),
            attempts=[CoreRunAttempt(core_run_id=core_run_id, status="created")],
        )

    def build_generation_metrics(
        self,
        config: InspectionRouteConfig,
        statistics: CaseGenerationStatistics,
        *,
        duplicate_cases: int,
        core_cases: int,
    ) -> InspectionGenerationMetrics:
        return InspectionGenerationMetrics(
            declared_scenarios=large_non_negative_integer(len(config.study.scenarios)),
            valid_scenarios=large_non_negative_integer(statistics.valid_selections),
            invalid_scenarios=large_non_negative_integer(statistics.invalid_combinations),
            duplicate_constraint_sets=large_non_negative_integer(duplicate_cases),
            core_cases=large_non_negative_integer(core_cases),
        )

    def interpret(
        self,
        report: ReportSummary,
        config: InspectionRouteConfig,
        context: InspectionRouteProjectionContext,
        *,
        run_id: str,
        domain_experiment_id: str,
        case: ProjectedCase | None = None,
    ) -> InspectionConstraintSetResult:
        if case is None:
            raise DomainExtensionError("La interpretación requiere el escenario proyectado.")
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
        config: InspectionRouteConfig,
        context: InspectionRouteProjectionContext,
        manifest: object,
        case_results: list[BaseModel],
    ) -> InspectionRouteResult:
        domain_manifest = (
            manifest
            if isinstance(manifest, InspectionDomainRunManifest)
            else InspectionDomainRunManifest.model_validate(manifest)
        )
        validated = [
            item
            if isinstance(item, InspectionConstraintSetResult)
            else InspectionConstraintSetResult.model_validate(item)
            for item in case_results
        ]
        return build_result(config, context, domain_manifest, validated)

    def render_human(self, result: InspectionRouteResult) -> str:
        return render_human(result)

    def render_json(self, result: InspectionRouteResult) -> bytes:
        return render_json(result)

    def render_markdown(self, result: InspectionRouteResult) -> str:
        return render_markdown(result)

    @staticmethod
    def _context(config: InspectionRouteConfig) -> InspectionRouteProjectionContext:
        return InspectionRouteProjectionContext(
            schema_version="1.0.0",
            vertex_mapping=[
                LocationVertex(vertex=index, location_id=location.id)
                for index, location in enumerate(config.study.locations, start=1)
            ],
        )
