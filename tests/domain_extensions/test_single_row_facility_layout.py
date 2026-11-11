from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from itertools import permutations
from pathlib import Path

import pytest
from pydantic import ValidationError

from tesis_domain_extensions.application import DomainApplication
from tesis_domain_extensions.contracts.common import ProducerRef, large_non_negative_integer
from tesis_domain_extensions.contracts.projection import domain_experiment_id
from tesis_domain_extensions.contracts.results import RouteCount
from tesis_domain_extensions.domains.single_row_facility_layout.adapter import (
    SingleRowFacilityLayoutAdapter,
)
from tesis_domain_extensions.domains.single_row_facility_layout.analysis import (
    _classify,
    build_result,
)
from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
    DomainRunManifest,
    GenerationMetrics,
    LayoutForestResult,
    SingleRowExperimentProjection,
    SingleRowFacilityLayoutResult,
    SingleRowProjectionContext,
    StationVertex,
)
from tesis_domain_extensions.domains.single_row_facility_layout.interpretation import _count
from tesis_domain_extensions.domains.single_row_facility_layout.progress import (
    format_layout_case_progress,
)
from tesis_domain_extensions.domains.single_row_facility_layout.render import (
    _linear_forest_paths,
    _ordered_cases,
    render_human,
    render_markdown,
)
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_domain_extensions.metrics import exact_fraction, unrestricted_undirected_path_count
from tesis_domain_extensions.schema_generation import write_all_domain_schemas, write_domain_schemas
from tesis_proyect.application.commands import CoreCommands
from tesis_proyect.domain.hashing import instance_hash
from tesis_proyect.engines.reference import count_reference
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import InlineMetadata
from tesis_proyect.models.enums import ErrorCode
from tesis_proyect.models.execution import Instance


def _payload() -> dict[str, object]:
    return json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_text(
            encoding="utf-8"
        )
    )


def _cycle_payload() -> dict[str, object]:
    payload = _payload()
    study = payload["study"]
    assert isinstance(study, dict)
    study["stations"] = [
        {"id": f"s{number}", "name": f"Estación {number}"} for number in range(1, 9)
    ]
    study["components"] = [
        {"id": "c1", "station_ids": ["s1", "s2", "s3"], "utility": 1},
        {"id": "c10", "station_ids": ["s5", "s6", "s7", "s8"], "utility": 1},
        {"id": "c11", "station_ids": ["s5", "s8"], "utility": 1},
    ]
    study["designs"] = [{"id": "d1", "title": "Diseño 1", "base_component_ids": ["c1"]}]
    return payload


def _enumerated_count(stations: list[str], edges: list[tuple[str, str]]) -> int:
    required = {tuple(sorted(edge)) for edge in edges}
    count = 0
    for order in permutations(stations):
        if order > tuple(reversed(order)):
            continue
        present = {
            tuple(sorted((order[index], order[index + 1]))) for index in range(len(order) - 1)
        }
        count += required <= present
    return count


def _synthetic_layout_result(path: Path) -> SingleRowFacilityLayoutResult:
    adapter = SingleRowFacilityLayoutAdapter()
    config = adapter.parse_config(path.read_bytes())
    context = adapter.project(config).context
    generation = adapter.generate_cases(config, context)
    generated = list(generation.cases)
    stations = [station.id for station in config.study.stations]
    evidence = []
    seen: set[str] = set()
    for case in generated:
        if case.case_id in seen:
            continue
        seen.add(case.case_id)
        count = _enumerated_count(stations, case.payload.edges)
        evidence.append(
            LayoutForestResult(
                forest_id=case.case_id,
                origins=[case.origin],
                edges=case.payload.edges,
                core_run_id="11111111-1111-4111-8111-111111111111",
                feasibility="feasible",
                compatible_layout_count=RouteCount(
                    value=large_non_negative_integer(count),
                    method=ProducerRef(id="independent-enumeration", version="1"),
                    exact_value=None,
                    reference_value=large_non_negative_integer(count),
                    counting_convention="undirected_paths_reverse_identified",
                    comparison_status="not_applicable",
                ),
                technical_metrics=None,
                diagnostics=[],
                limitations=[],
            )
        )
    experiment_id = domain_experiment_id(config)
    metrics = GenerationMetrics(
        theoretical_combinations=large_non_negative_integer(
            generation.statistics.theoretical_combinations
        ),
        cycle_pruned_branches=large_non_negative_integer(
            generation.statistics.cycle_pruned_branches
        ),
        degree_pruned_branches=large_non_negative_integer(
            generation.statistics.degree_pruned_branches
        ),
        valid_selections=large_non_negative_integer(generation.statistics.valid_selections),
        invalid_combinations=large_non_negative_integer(generation.statistics.invalid_combinations),
        duplicate_forests=large_non_negative_integer(len(generated) - len(seen)),
        core_cases=large_non_negative_integer(len(seen)),
    )
    manifest = DomainRunManifest(
        schema_version="1.0.0",
        domain_run_id="22222222-2222-4222-8222-222222222222",
        domain_experiment_id=experiment_id,
        domain=config.domain,
        display_name=config.study.title,
        status="completed",
        generator_cursor=large_non_negative_integer(len(generated)),
        generation=metrics,
        cases=[],
        created_at="2026-08-25T00:00:00.000Z",
        updated_at="2026-08-25T00:00:00.000Z",
    )
    return build_result(config, context, manifest, evidence)


def test_unrestricted_count_is_closed_form_and_preserves_large_values() -> None:
    assert [unrestricted_undirected_path_count(n) for n in range(1, 7)] == [1, 1, 3, 12, 60, 360]
    for n in range(1, 7):
        instance = Instance(
            schema_version="1.0.0",
            n=n,
            vertex_base=1,
            edges=[],
            source_metadata=InlineMetadata(kind="inline"),
            instance_hash=instance_hash(n, ()),
        )
        reference = count_reference(instance, reference_max_n=6)
        assert reference.status == "success"
        assert reference.value == unrestricted_undirected_path_count(n)
    assert unrestricted_undirected_path_count(30) > 9_007_199_254_740_991
    with pytest.raises(ValueError):
        unrestricted_undirected_path_count(0)
    with pytest.raises(ValueError):
        exact_fraction(-1, 2)


def test_study_description_is_preserved_in_projection_and_result(tmp_path: Path) -> None:
    payload = _payload()
    study = payload["study"]
    assert isinstance(study, dict)
    study["description"] = "Evaluar alternativas del sector de internación"
    definition = tmp_path / "study.json"
    definition.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    adapter = SingleRowFacilityLayoutAdapter()
    config = adapter.parse_config(definition.read_bytes())
    projection_data = adapter.project(config)
    projection = SingleRowExperimentProjection(
        schema_version="1.0.0",
        domain_experiment_id=domain_experiment_id(config),
        created_at="2026-09-07T00:00:00.000Z",
        domain_config=config,
        projection_context=projection_data.context,
    )
    result = _synthetic_layout_result(definition)

    assert projection.domain_config.study.description == study["description"]
    assert result.study_description == study["description"]


@pytest.mark.parametrize("description", [None, "Descripción histórica"])
def test_projection_without_description_keeps_its_historical_identity(
    description: str | None,
) -> None:
    payload = _payload()
    study = payload["study"]
    assert isinstance(study, dict)
    study.pop("description", None)
    if description is not None:
        study["description"] = description
    historical_id = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    adapter = SingleRowFacilityLayoutAdapter()
    config = adapter.parse_config(json.dumps(payload).encode())
    context = adapter.project(config).context
    projection = {
        "schema_version": "1.0.0",
        "domain_experiment_id": historical_id,
        "created_at": "2026-09-01T00:00:00.000Z",
        "domain_config": payload,
        "projection_context": context.model_dump(mode="json"),
    }

    loaded = adapter.parse_projection_record(json.dumps(projection).encode())

    assert loaded.domain_experiment_id == historical_id
    assert loaded.domain_config.study.description == description
    study["attachments"] = [{"kind": "link", "url": "https://example.org/changed", "label": None}]
    with pytest.raises((ValueError, DomainExtensionError)):
        adapter.parse_projection_record(json.dumps(projection).encode())


def test_cycle_is_pruned_before_a_core_case_is_built() -> None:
    adapter = SingleRowFacilityLayoutAdapter()
    config = adapter.parse_config(json.dumps(_cycle_payload()).encode())
    projection = adapter.project(config)
    generation = adapter.generate_cases(config, projection.context)
    cases = list(generation.cases)
    assert [case.payload.component_ids for case in cases] == [
        ["c1"],
        ["c1", "c11"],
        ["c1", "c10"],
    ]
    assert generation.statistics.theoretical_combinations == 4
    assert generation.statistics.valid_selections == 3
    assert generation.statistics.cycle_pruned_branches == 1
    assert all(case.core_config.source.kind == "inline" for case in cases)


def test_generation_progress_counts_pruned_descendants() -> None:
    adapter = SingleRowFacilityLayoutAdapter()
    config = adapter.parse_config(json.dumps(_cycle_payload()).encode())
    progress: list[int] = []
    generation = adapter.generate_cases(
        config,
        adapter.project(config).context,
        on_progress=progress.append,
    )

    list(generation.cases)

    assert progress[-1] == 4
    assert generation.statistics.valid_selections == 3
    assert generation.statistics.invalid_combinations == 1


def test_valid_overlap_extends_a_path_and_degree_three_is_pruned() -> None:
    payload = _payload()
    study = payload["study"]
    assert isinstance(study, dict)
    study["components"] = [
        {"id": "base", "station_ids": ["s1", "s2", "s3"], "utility": 1},
        {"id": "extension", "station_ids": ["s3", "s4"], "utility": 1},
        {"id": "degree-three", "station_ids": ["s2", "s4"], "utility": 1},
    ]
    study["designs"] = [{"id": "d", "title": "Diseño", "base_component_ids": ["base"]}]
    adapter = SingleRowFacilityLayoutAdapter()
    config = adapter.parse_config(json.dumps(payload).encode())
    generation = adapter.generate_cases(config, adapter.project(config).context)
    cases = list(generation.cases)
    assert any(case.payload.edges == [("s1", "s2"), ("s2", "s3"), ("s3", "s4")] for case in cases)
    assert generation.statistics.degree_pruned_branches >= 1


def test_invalid_base_and_reversed_component_duplicates_fail_prepare() -> None:
    adapter = SingleRowFacilityLayoutAdapter()
    cycle = _payload()
    study = cycle["study"]
    assert isinstance(study, dict)
    study["components"] = [
        {"id": "a", "station_ids": ["s1", "s2", "s3"], "utility": 1},
        {"id": "b", "station_ids": ["s3", "s1"], "utility": 1},
    ]
    study["designs"] = [{"id": "d", "title": "Diseño", "base_component_ids": ["a", "b"]}]
    with pytest.raises(DomainExtensionError, match="base inv"):
        adapter.parse_config(json.dumps(cycle).encode())

    duplicate = _payload()
    duplicate_study = duplicate["study"]
    assert isinstance(duplicate_study, dict)
    components = duplicate_study["components"]
    assert isinstance(components, list)
    reversed_component = deepcopy(components[0])
    assert isinstance(reversed_component, dict)
    reversed_component["id"] = "reversed"
    reversed_component["station_ids"] = list(reversed(reversed_component["station_ids"]))
    components.append(reversed_component)
    with pytest.raises(DomainExtensionError, match="inválida"):
        adapter.parse_config(json.dumps(duplicate).encode())


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate-station",
        "duplicate-component-id",
        "unknown-station",
        "duplicate-design-id",
        "unknown-base",
        "legacy-variable-field",
        "too-many-stations",
        "repeated-station-in-component",
        "duplicate-base-reference",
    ],
)
def test_layout_contract_rejects_catalog_inconsistencies(mutation: str) -> None:
    payload = _payload()
    study = payload["study"]
    execution = payload["execution"]
    assert isinstance(study, dict) and isinstance(execution, dict)
    if mutation == "duplicate-station":
        study["stations"].append(deepcopy(study["stations"][0]))
    elif mutation == "duplicate-component-id":
        study["components"][1]["id"] = study["components"][0]["id"]
    elif mutation == "unknown-station":
        study["components"][0]["station_ids"][0] = "unknown"
    elif mutation == "duplicate-design-id":
        study["designs"].append(deepcopy(study["designs"][0]))
    elif mutation == "unknown-base":
        study["designs"][0]["base_component_ids"] = ["unknown"]
    elif mutation == "legacy-variable-field":
        study["variable_component_ids"] = ["right-chain"]
    elif mutation == "too-many-stations":
        execution["integer_limits"]["max_n"] = 3
    elif mutation == "repeated-station-in-component":
        study["components"][0]["station_ids"] = ["s1", "s1"]
    else:
        study["designs"][0]["base_component_ids"] = ["base-chain", "base-chain"]
    with pytest.raises(DomainExtensionError):
        SingleRowFacilityLayoutAdapter().parse_config(json.dumps(payload).encode())


def test_non_base_components_are_derived_and_degree_three_is_pruned() -> None:
    payload = _payload()
    study = payload["study"]
    assert isinstance(study, dict)
    study["stations"] = [
        {"id": f"s{number}", "name": f"Estación {number}"} for number in range(1, 9)
    ]
    study["components"] = [
        {"id": "c1", "station_ids": ["s1", "s2", "s3"], "utility": 1},
        {"id": "c2", "station_ids": ["s6", "s7", "s8"], "utility": 1},
        {"id": "c3", "station_ids": ["s3", "s8", "s5"], "utility": 1},
    ]
    study["designs"] = [{"id": "d1", "title": "Diseño 1", "base_component_ids": ["c1"]}]
    adapter = SingleRowFacilityLayoutAdapter()
    config = adapter.parse_config(json.dumps(payload).encode())
    generation = adapter.generate_cases(config, adapter.project(config).context)
    cases = list(generation.cases)
    assert adapter.theoretical_combinations(config) == 4
    assert [case.payload.component_ids for case in cases] == [
        ["c1"],
        ["c1", "c3"],
        ["c1", "c2"],
    ]
    assert generation.statistics.valid_selections == 3
    assert generation.statistics.degree_pruned_branches == 1


def test_each_design_derives_its_own_optional_components() -> None:
    payload = _payload()
    study = payload["study"]
    assert isinstance(study, dict)
    study["components"] = [
        {"id": "c1", "station_ids": ["s1", "s2"], "utility": 1},
        {"id": "c2", "station_ids": ["s3", "s4"], "utility": 1},
    ]
    study["designs"] = [
        {"id": "d1", "title": "Diseño 1", "base_component_ids": ["c1"]},
        {"id": "d2", "title": "Diseño 2", "base_component_ids": ["c1", "c2"]},
    ]
    adapter = SingleRowFacilityLayoutAdapter()
    config = adapter.parse_config(json.dumps(payload).encode())
    cases = list(adapter.generate_cases(config, adapter.project(config).context).cases)
    assert adapter.theoretical_combinations(config) == 3
    assert [(case.origin.design_id, case.origin.added_component_ids) for case in cases] == [
        ("d1", []),
        ("d1", ["c2"]),
        ("d2", []),
    ]


def test_projection_context_rejects_gaps_and_duplicate_stations() -> None:
    with pytest.raises(ValidationError):
        SingleRowProjectionContext(
            schema_version="1.0.0",
            vertex_mapping=[StationVertex(vertex=2, station_id="s1")],
        )
    with pytest.raises(ValidationError):
        SingleRowProjectionContext(
            schema_version="1.0.0",
            vertex_mapping=[
                StationVertex(vertex=1, station_id="s1"),
                StationVertex(vertex=2, station_id="s1"),
            ],
        )


def test_count_comparison_mapping_covers_single_match_mismatch_and_unavailable() -> None:
    exact = {
        "status": "success",
        "value": 5,
        "engine": {"id": "exact", "version": "1"},
        "counting_convention": "undirected_paths_reverse_identified",
        "metrics": {"duration_ms": 1, "candidates_examined": None},
    }
    reference = {
        "status": "success",
        "value": 5,
        "engine": {"id": "reference", "version": "1"},
        "counting_convention": "undirected_paths_reverse_identified",
        "metrics": {"duration_ms": 2, "candidates_examined": 12},
    }
    single, metrics = _count(
        {
            "methods": {"exact": exact, "reference": None},
            "comparison": {"status": "not_applicable"},
        }
    )
    assert isinstance(single, RouteCount) and single.value == 5 and metrics is None
    matched, metrics = _count(
        {
            "methods": {"exact": exact, "reference": reference},
            "comparison": {"status": "match"},
        }
    )
    assert matched is not None and matched.value == 5
    assert metrics is not None and metrics.candidates_examined == 12
    different = deepcopy(reference)
    different["value"] = 4
    mismatch, metrics = _count(
        {
            "methods": {"exact": exact, "reference": different},
            "comparison": {"status": "mismatch"},
        }
    )
    assert mismatch is not None and mismatch.value is None and metrics is None
    assert _count({"methods": {"exact": None, "reference": None}, "comparison": None}) == (
        None,
        None,
    )
    with pytest.raises(DomainExtensionError, match="comparación desconocida"):
        _count(
            {
                "methods": {"exact": exact, "reference": None},
                "comparison": {"status": "unknown"},
            }
        )


def test_equal_forests_have_one_case_id_and_keep_distinct_origins() -> None:
    payload = _payload()
    study = payload["study"]
    assert isinstance(study, dict)
    study["components"] = [{"id": "base", "station_ids": ["s1", "s2"], "utility": 1}]
    study["designs"] = [
        {"id": "d1", "title": "Diseño 1", "base_component_ids": ["base"]},
        {"id": "d2", "title": "Diseño 2", "base_component_ids": ["base"]},
    ]
    adapter = SingleRowFacilityLayoutAdapter()
    config = adapter.parse_config(json.dumps(payload).encode())
    generation = adapter.generate_cases(config, adapter.project(config).context)
    cases = list(generation.cases)
    assert len(cases) == 2
    assert cases[0].case_id == cases[1].case_id
    assert {case.origin.design_id for case in cases} == {"d1", "d2"}


def test_decisions_sharing_a_forest_keep_distinct_utility_and_case_identity(
    tmp_path: Path,
) -> None:
    payload = _payload()
    study = payload["study"]
    assert isinstance(study, dict)
    study["components"] = [
        {"id": "base", "station_ids": ["s1", "s2"], "utility": 10},
        {"id": "extension", "station_ids": ["s2", "s3"], "utility": 3},
        {"id": "whole-path", "station_ids": ["s1", "s2", "s3"], "utility": 9},
    ]
    study["designs"] = [{"id": "d1", "title": "Decision identity", "base_component_ids": ["base"]}]
    fixture = tmp_path / "shared-forest.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")

    result = _synthetic_layout_result(fixture)
    shared = [case for case in result.designs[0].cases if case.prescribed_edge_count == 2]

    assert len(shared) == 3
    assert len({case.forest_id for case in shared}) == 1
    assert len({case.case_id for case in shared}) == 3
    assert {int(case.utility) for case in shared} == {3, 9, 12}
    assert {int(case.total_utility) for case in shared} == {13, 19, 22}


def test_linear_forest_renderer_reconstructs_station_chains() -> None:
    assert _linear_forest_paths([("s2", "s3"), ("s5", "s4"), ("s2", "s1")]) == [
        "s1 — s2 — s3",
        "s4 — s5",
    ]


def test_case_progress_uses_visible_design_and_station_names() -> None:
    assert (
        format_layout_case_progress(
            design_title="Diseño de expedición",
            added_component_ids=["restriction-1"],
            component_station_ids={"restriction-1": ["station-a", "station-b"]},
            station_names={"station-a": "Recepción", "station-b": "Depósito"},
        )
        == "Diseño de expedición · restricciones agregadas: Recepción → Depósito"
    )
    assert (
        format_layout_case_progress(
            design_title="Diseño de expedición",
            added_component_ids=["restriccion-desconocida"],
            component_station_ids={},
            station_names={},
        )
        == "Diseño de expedición · restricciones agregadas: Restricción sin nombre"
    )


@pytest.mark.integration
def test_grouped_execution_runs_an_equal_forest_once(tmp_path: Path) -> None:
    payload = _payload()
    study = payload["study"]
    assert isinstance(study, dict)
    study["components"] = [{"id": "base", "station_ids": ["s1", "s2"], "utility": 1}]
    study["designs"] = [
        {"id": "d1", "title": "Diseño 1", "base_component_ids": ["base"]},
        {"id": "d2", "title": "Diseño 2", "base_component_ids": ["base"]},
    ]
    config_path = tmp_path / "study.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    core = CoreCommands.open(tmp_path)
    result = (
        DomainApplication(tmp_path, core)
        .run(DomainApplication(tmp_path, core).prepare(config_path).reference)
        .result
    )
    assert result.generation.theoretical_combinations == 2
    assert result.generation.valid_selections == 2
    assert result.generation.duplicate_forests == 1
    assert result.generation.core_cases == 1
    assert len(core.list_runs().runs) == 1
    assert len(result.designs) == 2
    first = result.designs[0].cases[0]
    second = result.designs[1].cases[0]
    assert first.case_id != second.case_id
    assert first.forest_id == second.forest_id
    assert first.core_run_id == second.core_run_id


@pytest.mark.integration
def test_grouped_execution_deduplicates_core_cases_and_renders_without_new_runs(
    tmp_path: Path,
) -> None:
    core = CoreCommands.open(tmp_path)
    application = DomainApplication(tmp_path, core)
    prepared = application.prepare(
        Path("examples/domains/single-row-facility-layout/comparison.json")
    )
    interpreted = application.run(prepared.reference)
    assert interpreted.result.generation.theoretical_combinations == 2
    assert interpreted.result.generation.core_cases == 2
    assert interpreted.result.designs[0].pareto_case_ids
    manifest = interpreted.manifest
    core_run_count = len(core.list_runs().runs)
    rendered = application.render(manifest.domain_run_id)
    assert len(core.list_runs().runs) == core_run_count
    assert rendered.result == interpreted.result
    human = render_human(rendered.result)
    markdown = render_markdown(rendered.result)
    assert "Medida: Disponibilidad de disposiciones respecto del dise" in human
    assert "Frontera de Pareto" in human
    assert "no determina el mejor layout industrial" not in human
    assert "### Casos no v" in markdown
    assert "### Casos v" in markdown
    assert "### Frontera de Pareto" in markdown
    assert "| 1/1 (100.00 %) |" in markdown
    listing = application.list_runs(
        experiment_reference=prepared.reference,
        domain_id="single-row-facility-layout",
        prefix=manifest.domain_run_id.replace("-", "")[:8],
    )
    assert [item.run_id for item in listing.runs] == [manifest.domain_run_id]
    unfiltered = application.list_runs(
        experiment_reference=None,
        domain_id=None,
        prefix=None,
    )
    assert manifest.domain_run_id in {item.run_id for item in unfiltered.runs}
    assert (tmp_path / "domain_runs" / manifest.domain_run_id / "domain_run.json").is_file()


def test_layout_render_explains_case_metrics_and_orders_by_total_utility() -> None:
    result = _synthetic_layout_result(
        Path("examples/domains/single-row-facility-layout/hospital-k8.json")
    )
    design = result.designs[0]
    markdown = render_markdown(result)
    human = render_human(result)
    ordered = _ordered_cases(design.cases)

    assert [int(case.total_utility) for case in ordered] == sorted(
        (int(case.total_utility) for case in design.cases), reverse=True
    )
    assert (
        "| Caso | Dise\u00f1o y componentes del caso | Bosque | Utilidad incremental |" in markdown
    )
    assert "Dise\u00f1o: **Sector hospitalario** (`d1`)" in markdown
    assert "Base/obligatorios: `c0`<br>A\u00f1adidos: ninguno" in markdown
    assert "**Utilidad incremental:** suma de utilidades" in markdown
    assert "**Utilidad total:** utilidad de los componentes base" in markdown
    assert "**Disponibilidad:** `H_i/H_D`" in markdown
    assert "**Restrictividad:** `1 - H_i/H_D`" in markdown
    assert "### Dominancia y frontera de Pareto" in markdown
    assert "Una alternativa A **domina** a B" in markdown
    assert "el mismo orden de dominancia porque la utilidad de la base es constante" in markdown
    assert "no puede mejorarse un objetivo sin empeorar al menos el otro" in markdown
    assert (
        markdown.index("### Dominancia y frontera de Pareto")
        < markdown.index("### Casos v\u00e1lidos dominados")
        < markdown.index("### Frontera de Pareto")
    )
    assert "P2" not in markdown
    assert "\u222a" not in markdown
    assert "Utilidad total: " in human
    assert "= 10 (base) +" in human
    assert "Disponibilidad H_i/H_D:" in human
    assert "Restrictividad 1 - H_i/H_D:" in human
    assert "A\u00f1adidos: ninguno" in human
    assert "Dominancia y frontera de Pareto:" in human
    assert "A domina a B si tiene utilidad total y layouts al menos iguales" in human
    assert "no puede mejorarse un objetivo sin empeorar al menos el otro" in human
    assert "P2" not in human


@pytest.mark.integration
def test_grouped_resume_continues_from_the_persisted_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = CoreCommands.open(tmp_path)
    application = DomainApplication(tmp_path, core)
    prepared = application.prepare(
        Path("examples/domains/single-row-facility-layout/comparison.json")
    )
    original_run = core.run
    calls = 0

    def interrupt_second_run(reference: str):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OperationalError(ErrorCode.IO_ERROR, "simulated interruption")
        return original_run(reference)

    monkeypatch.setattr(core, "run", interrupt_second_run)
    with pytest.raises(DomainExtensionError, match="tesis-domain resume"):
        application.run(prepared.reference)
    manifest, _ = application.store.list_domain_runs()[0]
    assert int(manifest.generator_cursor) == 2
    monkeypatch.setattr(core, "run", original_run)
    resumed = application.resume(manifest.domain_run_id)
    assert resumed.manifest.status == "completed"
    assert int(resumed.manifest.generator_cursor) == 2
    assert len(core.list_runs().runs) == 2


def test_hospital_k8_matches_the_application_case_and_pareto_frontier() -> None:
    result = _synthetic_layout_result(
        Path("examples/domains/single-row-facility-layout/hospital-k8.json")
    )
    design = result.designs[0]
    assert design.theoretical_combinations == 32
    assert design.valid_case_count == 21
    assert design.invalid_combination_count == 11
    assert design.base_layout_count is not None
    assert design.base_layout_count.value == 5040
    assert design.invalid_combinations is not None
    assert len(design.invalid_combinations) == 11
    pareto = {
        tuple(case.added_component_ids): (
            case.utility,
            case.compatible_layout_count.value if case.compatible_layout_count else None,
        )
        for case in design.cases
        if case.pareto_optimal
    }
    assert pareto == {
        (): (0, 5040),
        ("c1",): (9, 1440),
        ("c1", "c4"): (17, 240),
        ("c1", "c2", "c4"): (24, 48),
    }
    case_a = next(case for case in design.cases if case.added_component_ids == ["c1", "c2", "c4"])
    assert case_a.total_utility == 34
    assert case_a.availability_ratio is not None
    assert (case_a.availability_ratio.numerator, case_a.availability_ratio.denominator) == (
        1,
        105,
    )
    assert result.generation.degree_pruned_branches == 8
    assert result.generation.invalid_combinations == 11


def test_industrial_k8_has_the_expected_non_trivial_frontier() -> None:
    result = _synthetic_layout_result(
        Path("examples/domains/single-row-facility-layout/industrial-k8.json")
    )
    design = result.designs[0]
    assert (design.theoretical_combinations, design.valid_case_count) == (64, 34)
    assert design.invalid_combination_count == 30
    assert design.invalid_combinations is None
    pareto = {
        tuple(case.added_component_ids): (
            case.utility,
            case.compatible_layout_count.value if case.compatible_layout_count else None,
        )
        for case in design.cases
        if case.pareto_optimal
    }
    assert pareto == {
        (): (0, 5040),
        ("c2",): (8, 1440),
        ("c2", "c4"): (14, 480),
        ("c2", "c3"): (15, 240),
        ("c2", "c3", "c4"): (21, 96),
        ("c2", "c3", "c4", "c6"): (25, 24),
    }


def test_pareto_ties_zero_utility_and_inconclusive_counts_are_conservative() -> None:
    result = _synthetic_layout_result(
        Path("examples/domains/single-row-facility-layout/hospital-k8.json")
    )
    cases = result.designs[0].cases
    base = next(case for case in cases if not case.added_component_ids)
    constrained = next(case for case in cases if case.added_component_ids == ["c3"])
    zero_utility = constrained.model_copy(
        update={"utility": 0, "dominated": None, "pareto_optimal": None}
    )
    classified, pareto_ids = _classify(
        [base.model_copy(update={"dominated": None, "pareto_optimal": None}), zero_utility]
    )
    assert classified[0].pareto_optimal is True
    assert classified[1].dominated is True
    assert pareto_ids == [base.case_id]

    tied = base.model_copy(
        update={
            "case_id": "f" * 64,
            "dominated": None,
            "pareto_optimal": None,
        }
    )
    classified, pareto_ids = _classify(
        [base.model_copy(update={"dominated": None, "pareto_optimal": None}), tied]
    )
    assert all(case.pareto_optimal for case in classified)
    assert set(pareto_ids) == {base.case_id, tied.case_id}

    inconclusive = tied.model_copy(
        update={"compatible_layout_count": None, "dominated": None, "pareto_optimal": None}
    )
    classified, pareto_ids = _classify([base, inconclusive])
    assert pareto_ids == []
    assert classified[1].pareto_optimal is None


@pytest.mark.parametrize("invalid_utility", [-1, 1.5, True])
def test_utility_is_a_required_non_negative_integer(invalid_utility: object) -> None:
    payload = _payload()
    payload["study"]["components"][0]["utility"] = invalid_utility
    with pytest.raises(DomainExtensionError):
        SingleRowFacilityLayoutAdapter().parse_config(json.dumps(payload).encode())


def test_reporting_policy_is_required() -> None:
    payload = _payload()
    del payload["reporting"]
    with pytest.raises(DomainExtensionError):
        SingleRowFacilityLayoutAdapter().parse_config(json.dumps(payload).encode())


def test_schema_generation_routes_every_catalog_entry(tmp_path: Path) -> None:
    write_all_domain_schemas(tmp_path)
    assert (tmp_path / "inspection-route" / "1.0.0").is_dir()
    assert (tmp_path / "single-row-facility-layout" / "1.0.0").is_dir()
    with pytest.raises(ValueError, match="unknown domain schema catalog"):
        write_domain_schemas(tmp_path / "unknown", domain_id="unknown", version="1.0.0")


def test_evidence_changes_identity_but_preserves_scientific_results(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    documented = tmp_path / "documented.json"
    payload = _payload()
    baseline.write_text(json.dumps(payload), encoding="utf-8")
    study = payload["study"]
    assert isinstance(study, dict)
    for entity in [study, *study["components"], *study["designs"]]:
        entity["description"] = "Justificación"
        entity["attachments"] = [
            {"kind": "link", "url": "https://example.org/technical", "label": "Referencia"}
        ]
    documented.write_text(json.dumps(payload), encoding="utf-8")
    adapter = SingleRowFacilityLayoutAdapter()
    assert domain_experiment_id(
        adapter.parse_config(baseline.read_bytes())
    ) != domain_experiment_id(adapter.parse_config(documented.read_bytes()))
    before = _synthetic_layout_result(baseline)
    after = _synthetic_layout_result(documented)
    for original, updated in zip(before.designs, after.designs, strict=True):
        assert original.base_layout_count == updated.base_layout_count
        updated_by_components = {tuple(sorted(case.component_ids)): case for case in updated.cases}
        assert {tuple(sorted(case.component_ids)) for case in original.cases} == set(
            updated_by_components
        )
        for left in original.cases:
            right = updated_by_components[tuple(sorted(left.component_ids))]
            assert (
                left.utility,
                left.total_utility,
                left.compatible_layout_count,
                left.availability_ratio,
                left.pareto_optimal,
            ) == (
                right.utility,
                right.total_utility,
                right.compatible_layout_count,
                right.availability_ratio,
                right.pareto_optimal,
            )
