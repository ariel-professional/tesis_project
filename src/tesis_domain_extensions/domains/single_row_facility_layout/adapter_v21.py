from __future__ import annotations

import json
from typing import Any, ClassVar, cast

from pydantic import BaseModel, ValidationError

from tesis_domain_extensions.domains.single_row_facility_layout.adapter_v2 import (
    SingleRowFacilityLayoutAdapterV2,
)
from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v21 import (
    ArchivedFastDomainRunManifestV21,
    ArchivedFastExperimentProjectionV21,
    DomainRunManifestV21,
    FastResultSummaryV21,
    SingleRowDomainRefV21,
    SingleRowExperimentProjectionV21,
    SingleRowExperimentSummaryV21,
    SingleRowFacilityLayoutConfigV21,
    SingleRowFacilityLayoutResultV21,
    SingleRowProjectionContextV21,
    SingleRowRunSummaryV21,
    normalize_archived_fast_config,
)
from tesis_domain_extensions.errors import DomainExtensionError, invalid_domain_config


class SingleRowFacilityLayoutAdapterV21(SingleRowFacilityLayoutAdapterV2):
    version = "2.1.0"
    description = "Ejecución estándar y de alto rendimiento para disposiciones lineales"
    projection_model = SingleRowExperimentProjectionV21  # type: ignore[assignment]
    legacy_projection_model = ArchivedFastExperimentProjectionV21
    result_model = SingleRowFacilityLayoutResultV21  # type: ignore[assignment]
    fast_result_model = FastResultSummaryV21
    domain_run_model = DomainRunManifestV21  # type: ignore[assignment]
    legacy_domain_run_model = ArchivedFastDomainRunManifestV21
    experiment_summary_model = SingleRowExperimentSummaryV21  # type: ignore[assignment]
    run_summary_model = SingleRowRunSummaryV21  # type: ignore[assignment]
    schema_models: ClassVar[dict[str, type[BaseModel]]] = {
        "domain-experiment-config.schema.json": SingleRowFacilityLayoutConfigV21,
        "domain-experiment-projection.schema.json": SingleRowExperimentProjectionV21,
        "domain-experiment-summary.schema.json": SingleRowExperimentSummaryV21,
        "domain-run-summary.schema.json": SingleRowRunSummaryV21,
        "domain-run-manifest.schema.json": DomainRunManifestV21,
        "single-row-facility-layout-result.schema.json": SingleRowFacilityLayoutResultV21,
        "single-row-fast-result-summary.schema.json": FastResultSummaryV21,
    }

    def parse_config(self, payload: bytes) -> SingleRowFacilityLayoutConfigV21:
        if payload.startswith(b"\xef\xbb\xbf"):
            raise DomainExtensionError("La configuración no puede contener UTF-8 BOM.")
        try:
            return SingleRowFacilityLayoutConfigV21.model_validate_json(payload)
        except ValidationError as exc:
            try:
                archived = normalize_archived_fast_config(json.loads(payload))
                return SingleRowFacilityLayoutConfigV21.model_validate(archived)
            except (UnicodeDecodeError, ValueError, ValidationError):
                raise invalid_domain_config(exc) from exc

    def build_projection_record(
        self,
        *,
        domain_experiment_id: str,
        created_at: str,
        config: Any,
        context: Any,
        instance_nonce: str | None,
    ) -> SingleRowExperimentProjectionV21:
        from tesis_domain_extensions.domains.single_row_facility_layout.objectives.catalog import (
            selected_objective_snapshots,
        )

        return SingleRowExperimentProjectionV21(
            schema_version="2.1.0",
            domain_experiment_id=domain_experiment_id,
            created_at=created_at,
            instance_nonce=instance_nonce,
            domain_config=config,
            projection_context=context,
            objective_snapshots=selected_objective_snapshots(config.decision_model),
        )

    def parse_projection_record(self, payload: bytes) -> SingleRowExperimentProjectionV21:
        try:
            return SingleRowExperimentProjectionV21.model_validate_json(
                payload,
                context={"historical_projection": True},
            )
        except ValidationError:
            return ArchivedFastExperimentProjectionV21.model_validate_json(payload)  # type: ignore[return-value]

    @staticmethod
    def _context(config: Any) -> SingleRowProjectionContextV21:
        from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
            StationVertexV2,
        )

        return SingleRowProjectionContextV21(
            schema_version="2.1.0",
            vertex_mapping=[
                StationVertexV2(vertex=index, station_id=item.id)
                for index, item in enumerate(config.study.stations, start=1)
            ],
        )

    def build_grouped_result(
        self,
        config: Any,
        context: Any,
        manifest: Any,
        case_results: list[BaseModel],
    ) -> SingleRowFacilityLayoutResultV21:
        from tesis_domain_extensions.domains.single_row_facility_layout.analysis_v2 import (
            _case_values,
            build_result_v2,
        )
        from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
            LayoutForestResult,
        )
        from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
            SingleRowFacilityLayoutConfigV2,
            SingleRowProjectionContextV2,
        )
        from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v21 import (
            LayoutCaseResultV21,
        )

        validated = [
            item
            if isinstance(item, LayoutForestResult)
            else LayoutForestResult.model_validate(item)
            for item in case_results
        ]
        config_payload = cast(Any, config).model_dump(mode="python")
        config_payload["schema_version"] = "2.0.0"
        config_payload["domain"]["version"] = "2.0.0"
        config_payload["execution"].pop("mode", None)
        config_v2 = SingleRowFacilityLayoutConfigV2.model_validate(config_payload)
        context_payload = cast(Any, context).model_dump(mode="python")
        context_payload["schema_version"] = "2.0.0"
        context_v2 = SingleRowProjectionContextV2.model_validate(context_payload)
        base = build_result_v2(config_v2, context_v2, manifest, validated)
        payload = base.model_dump(mode="python")
        for design in payload["designs"]:
            for case in design["cases"]:
                case["counting_producer"] = {
                    "id": "linear-forest-closed-form",
                    "version": "1",
                }
                case["scientific_status"] = (
                    "inconclusive" if case["feasibility"] == "inconclusive" else "conclusive"
                )
                case["criteria_vector"] = {
                    key: {"numerator": value.numerator, "denominator": value.denominator}
                    for key, value in _case_values(LayoutCaseResultV21.model_validate(case)).items()
                }
        payload["schema_version"] = "2.1.0"
        payload["domain"] = SingleRowDomainRefV21(
            id="single-row-facility-layout", version="2.1.0"
        ).model_dump(mode="json")
        return SingleRowFacilityLayoutResultV21.model_validate(payload)

    def execute_high_performance(self, application: Any, loaded: Any, manifest: Any) -> Any:
        from tesis_domain_extensions.domains.single_row_facility_layout.fast_execution import (
            execute_fast_run,
        )

        return execute_fast_run(application, loaded, manifest)

    def query_high_performance(
        self, application: Any, manifest: Any, adapter: Any, operation: str, params: Any
    ) -> Any:
        from tesis_domain_extensions.domains.single_row_facility_layout.fast_execution import (
            query_fast_result,
        )

        return query_fast_result(application, manifest, adapter, operation, params)

    def render_human(self, result: Any) -> str:
        if isinstance(result, FastResultSummaryV21):
            count = sum(int(item.valid_case_count) for item in result.designs)
            return f"{result.study_title}: {count} casos (alto rendimiento)"
        return super().render_human(result)

    def render_json(self, result: Any) -> bytes:
        return cast(bytes, result.model_dump_json(indent=2).encode("utf-8"))

    def render_markdown(self, result: Any) -> str:
        if not isinstance(result, FastResultSummaryV21):
            return super().render_markdown(result)
        return "\n".join(
            [
                f"# {result.study_title}",
                "",
                "## Criterios",
                *[f"- {item.definition.name}" for item in result.objective_snapshots],
                "",
                "## Ejecución",
                "Modo de alto rendimiento; el detalle de casos se consulta mediante índices.",
            ]
        )
