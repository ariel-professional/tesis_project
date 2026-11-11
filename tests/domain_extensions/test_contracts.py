from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from tesis_domain_extensions.catalog import build_catalog, resolve_adapter
from tesis_domain_extensions.contracts.common import ProducerRef
from tesis_domain_extensions.contracts.projection import domain_experiment_id
from tesis_domain_extensions.contracts.results import RouteCount
from tesis_domain_extensions.domains.inspection_route.adapter import InspectionRouteAdapter
from tesis_domain_extensions.domains.inspection_route.analysis import build_result
from tesis_domain_extensions.domains.inspection_route.contracts import (
    InspectionConstraintSetResult,
    InspectionDomainRunManifest,
    InspectionGenerationMetrics,
    InspectionRouteConfig,
    InspectionRouteProjection,
    InspectionRouteProjectionContext,
)
from tesis_domain_extensions.domains.inspection_route.render import (
    render_human,
    render_markdown,
)
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_domain_extensions.metrics import exact_fraction, unrestricted_undirected_path_count
from tesis_domain_extensions.schema_generation import DOMAIN_SCHEMA_CATALOG, schema_bytes
from tests.domain_extensions.conftest import RUN_ID


def _interpret(
    report: dict[str, object],
    config: InspectionRouteConfig,
    context: InspectionRouteProjectionContext,
):
    case = next(InspectionRouteAdapter().iter_cases(config, context))
    return InspectionRouteAdapter().interpret(
        report,
        config,
        context,
        run_id=RUN_ID,
        domain_experiment_id=case.core_experiment_id,
        case=case,
    )


def test_inspection_study_is_strict_canonical_and_validates_references(
    partial_config: InspectionRouteConfig,
) -> None:
    payload = partial_config.model_dump(mode="python")
    assert payload["study"]["scenarios"][0]["required_consecutive_visits"] == [
        ("bombas", "calderas"),
        ("deposito", "laboratorio"),
    ]
    invalid_payloads = []
    extra = deepcopy(payload)
    extra["noise"] = True
    invalid_payloads.append(extra)
    duplicate_location = deepcopy(payload)
    duplicate_location["study"]["locations"].append(duplicate_location["study"]["locations"][0])
    invalid_payloads.append(duplicate_location)
    duplicate_scenario = deepcopy(payload)
    duplicate_scenario["study"]["scenarios"].append(duplicate_scenario["study"]["scenarios"][0])
    invalid_payloads.append(duplicate_scenario)
    unknown = deepcopy(payload)
    unknown["study"]["scenarios"][0]["required_consecutive_visits"] = [("missing", "deposito")]
    invalid_payloads.append(unknown)
    self_pair = deepcopy(payload)
    self_pair["study"]["scenarios"][0]["required_consecutive_visits"] = [("deposito", "deposito")]
    invalid_payloads.append(self_pair)
    inverse = deepcopy(payload)
    inverse["study"]["scenarios"][0]["required_consecutive_visits"].append(("calderas", "bombas"))
    invalid_payloads.append(inverse)
    one_scenario = deepcopy(payload)
    one_scenario["study"]["scenarios"] = one_scenario["study"]["scenarios"][:1]
    invalid_payloads.append(one_scenario)
    too_large = deepcopy(payload)
    too_large["execution"]["integer_limits"]["max_n"] = 7
    invalid_payloads.append(too_large)
    for invalid in invalid_payloads:
        with pytest.raises(ValidationError):
            InspectionRouteConfig.model_validate(invalid)


def test_projection_is_deterministic_reversible_and_grouped(
    partial_config: InspectionRouteConfig,
) -> None:
    adapter = InspectionRouteAdapter()
    first = adapter.project(partial_config)
    second = adapter.project(partial_config)
    assert first == second
    assert first.core_config is None
    assert [item.location_id for item in first.context.vertex_mapping] == [
        item.id for item in partial_config.study.locations
    ]
    instance_nonce = "a" * 32
    record = adapter.build_projection_record(
        domain_experiment_id=domain_experiment_id(partial_config, instance_nonce),
        created_at="2026-08-29T12:00:00.000Z",
        config=partial_config,
        context=first.context,
        instance_nonce=instance_nonce,
    )
    assert InspectionRouteProjection.model_validate(record) == record


def test_domain_experiment_hash_is_canonical_and_projection_is_self_contained(
    partial_config: InspectionRouteConfig,
) -> None:
    compact = json.dumps(partial_config.model_dump(mode="json"), separators=(",", ":"))
    pretty = json.dumps(partial_config.model_dump(mode="json"), indent=4, sort_keys=True)
    adapter = InspectionRouteAdapter()
    assert domain_experiment_id(adapter.parse_config(compact.encode())) == domain_experiment_id(
        adapter.parse_config(pretty.encode())
    )


def test_generation_omits_invalid_scenario_and_keeps_progress(
    partial_config: InspectionRouteConfig,
    projection_context: InspectionRouteProjectionContext,
) -> None:
    progress: list[int] = []
    generation = InspectionRouteAdapter().generate_cases(
        partial_config,
        projection_context,
        on_progress=progress.append,
    )
    cases = list(generation.cases)
    assert len(cases) == 3
    assert progress == [1, 2, 3, 4]
    assert generation.statistics.valid_selections == 3
    assert generation.statistics.invalid_combinations == 1
    assert {case.origin.scenario_id for case in cases} == {
        "procedimientos-independientes",
        "recorrido-libre",
        "recorrido-fijado",
    }

    cycle_payload = partial_config.model_dump(mode="python")
    cycle_payload["study"]["scenarios"][-1]["required_consecutive_visits"] = [
        ("bombas", "calderas"),
        ("calderas", "tablero"),
        ("bombas", "tablero"),
    ]
    cycle_config = InspectionRouteConfig.model_validate(cycle_payload)
    cycle_generation = InspectionRouteAdapter().generate_cases(
        cycle_config,
        InspectionRouteAdapter().project(cycle_config).context,
    )
    list(cycle_generation.cases)
    assert cycle_generation.statistics.cycle_pruned_branches == 1


def test_unrestricted_universe_and_exact_fraction_boundaries() -> None:
    assert unrestricted_undirected_path_count(1) == 1
    assert unrestricted_undirected_path_count(8) == 20160
    assert exact_fraction(1440, 20160).model_dump() == {
        "numerator": 1,
        "denominator": 14,
    }
    for invalid_n in (True, 0, 1.5):
        with pytest.raises(ValueError):
            unrestricted_undirected_path_count(invalid_n)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        exact_fraction(-1, 1)
    with pytest.raises(ValueError):
        exact_fraction(0, 0)


def test_interpretation_maps_structure_count_and_metrics(
    partial_config: InspectionRouteConfig,
    projection_context: InspectionRouteProjectionContext,
    success_report: dict[str, object],
) -> None:
    result = _interpret(success_report, partial_config, projection_context)
    assert result.feasibility == "feasible"
    assert result.structure is not None
    assert result.structure.mandatory_chains == [
        ["bombas", "calderas"],
        ["laboratorio", "deposito"],
    ]
    assert result.structure.planning_blocks == 6
    assert result.route_count is not None and result.route_count.value == 1440
    assert result.technical_metrics is not None
    assert result.technical_metrics.candidates_examined == 20160


def test_comparative_result_highlights_maximum_and_local_invalid(
    partial_config: InspectionRouteConfig,
    projection_context: InspectionRouteProjectionContext,
) -> None:
    adapter = InspectionRouteAdapter()
    cases = list(adapter.iter_cases(partial_config, projection_context))
    counts = [1440, 20160, 1]
    evidences = [
        InspectionConstraintSetResult(
            constraint_set_id=case.case_id,
            origins=[case.origin],
            required_consecutive_visits=case.payload.required_consecutive_visits,
            core_run_id=f"12345678-1234-4234-8234-123456789ab{index}",
            feasibility="feasible",
            structure=None,
            route_count=RouteCount(
                value=count,
                method=ProducerRef(id="bruteforce-python", version="1"),
                exact_value=None,
                reference_value=count,
                counting_convention="undirected_paths_reverse_identified",
                comparison_status="not_applicable",
            ),
            technical_metrics=None,
            diagnostics=[],
            limitations=[],
        )
        for index, (case, count) in enumerate(zip(cases, counts, strict=True))
    ]
    manifest = InspectionDomainRunManifest(
        schema_version="1.0.0",
        domain_run_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        domain_experiment_id=domain_experiment_id(partial_config),
        domain=partial_config.domain,
        display_name=partial_config.study.title,
        status="completed",
        generator_cursor=3,
        generation=InspectionGenerationMetrics(
            declared_scenarios=4,
            valid_scenarios=3,
            invalid_scenarios=1,
            duplicate_constraint_sets=0,
            core_cases=3,
        ),
        cases=[],
        created_at="2026-08-29T12:00:00.000Z",
        updated_at="2026-08-29T12:01:00.000Z",
    )
    result = build_result(partial_config, projection_context, manifest, evidences)
    assert result.comparison_status == "conclusive"
    assert result.most_flexible_scenario_ids == ["recorrido-libre"]
    assert [item.route_count.value if item.route_count else None for item in result.scenarios] == [
        1440,
        20160,
        1,
        None,
    ]
    assert result.scenarios[-1].validation_issue is not None
    assert result.scenarios[-1].core_run_id is None
    assert "máxima flexibilidad" in render_human(result)
    assert "Ejecución CORE: **omitida**" in render_markdown(result)

    inconclusive_evidence = [
        evidences[0].model_copy(update={"route_count": None}),
        *evidences[1:],
    ]
    inconclusive = build_result(
        partial_config,
        projection_context,
        manifest,
        inconclusive_evidence,
    )
    assert inconclusive.comparison_status == "inconclusive"
    assert inconclusive.most_flexible_scenario_ids == []
    assert "Máxima flexibilidad: no determinada" in render_human(inconclusive)

    with pytest.raises(DomainExtensionError, match="ejecución terminal"):
        build_result(
            partial_config,
            projection_context,
            manifest.model_copy(update={"status": "running"}),
            evidences,
        )
    with pytest.raises(DomainExtensionError, match="Falta evidencia CORE"):
        build_result(partial_config, projection_context, manifest, evidences[1:])
    oversized = evidences[0].model_copy(
        update={
            "route_count": evidences[0].route_count.model_copy(update={"value": 20161})
            if evidences[0].route_count is not None
            else None
        }
    )
    with pytest.raises(DomainExtensionError, match="universo irrestricto"):
        build_result(
            partial_config,
            projection_context,
            manifest,
            [oversized, *evidences[1:]],
        )


def test_measure_requires_conclusive_core_comparison(
    partial_config: InspectionRouteConfig,
    projection_context: InspectionRouteProjectionContext,
    success_report: dict[str, object],
) -> None:
    matching = deepcopy(success_report)
    matching["methods"]["exact"] = {  # type: ignore[index]
        "status": "success",
        "value": 1440,
        "engine": {"id": "exact", "version": "1"},
        "counting_convention": "undirected_paths_reverse_identified",
        "metrics": {"duration_ms": 1, "candidates_examined": None},
    }
    matching["comparison"] = {"status": "match"}
    matched = _interpret(matching, partial_config, projection_context)
    assert matched.route_count is not None and matched.route_count.value == 1440
    mismatch = deepcopy(matching)
    mismatch["methods"]["exact"]["value"] = 1441  # type: ignore[index]
    mismatch["comparison"] = {"status": "mismatch"}
    inconclusive = _interpret(mismatch, partial_config, projection_context)
    assert inconclusive.route_count is not None
    assert inconclusive.route_count.value is None


def test_catalog_rejects_duplicates_incomplete_and_unknown_domain(
    partial_config: InspectionRouteConfig,
) -> None:
    adapter = InspectionRouteAdapter()
    with pytest.raises(ValueError, match="duplicate"):
        build_catalog((adapter, adapter))

    class Incomplete:
        domain_id = "inspection-route"
        version = "1.0.0"

    with pytest.raises(ValueError, match="incomplete"):
        build_catalog((Incomplete(),))  # type: ignore[arg-type]
    payload = partial_config.model_dump(mode="json")
    payload["domain"] = {"id": "unknown", "version": "1.0.0"}
    with pytest.raises(DomainExtensionError, match="no está soportado"):
        resolve_adapter(json.dumps(payload).encode())


def test_domain_schemas_have_no_drift() -> None:
    for (domain_id, version), schemas in DOMAIN_SCHEMA_CATALOG.items():
        root = Path("domain_schemas") / domain_id / version
        assert {path.name for path in root.glob("*.json")} == set(schemas)
        for name, model in schemas.items():
            assert (root / name).read_bytes() == schema_bytes(model)
