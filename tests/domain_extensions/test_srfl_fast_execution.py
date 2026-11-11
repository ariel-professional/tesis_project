from __future__ import annotations

import json
from fractions import Fraction
from itertools import product
from pathlib import Path

import pytest

from tesis_domain_extensions.application import DomainApplication
from tesis_domain_extensions.domains.single_row_facility_layout import (
    fast_execution as fast_execution_module,
)
from tesis_domain_extensions.domains.single_row_facility_layout.adapter_v21 import (
    SingleRowFacilityLayoutAdapterV21,
)
from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v21 import (
    SingleRowFacilityLayoutConfigV21,
)
from tesis_domain_extensions.domains.single_row_facility_layout.fast_execution import (
    classify_fast_frontier,
    evaluate_fast_cases,
)
from tesis_domain_extensions.domains.single_row_facility_layout.fast_result_store import (
    FastResultReader,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.pareto import (
    ParetoPoint,
    classify_pareto,
)
from tesis_domain_extensions.errors import DomainExtensionError, DomainRunCancelled
from tesis_proyect.application.commands import CoreCommands


def test_fast_case_pass_counts_and_persists_without_core_run_ids(tmp_path: Path) -> None:
    payload = json.loads(
        Path("examples/domains/single-row-facility-layout/v2-complete.json").read_text(
            encoding="utf-8"
        )
    )
    payload["schema_version"] = "2.1.0"
    payload["domain"]["version"] = "2.1.0"
    config = SingleRowFacilityLayoutConfigV21.model_validate(payload)
    context = SingleRowFacilityLayoutAdapterV21().project(config).context
    run_directory = tmp_path / "domain_runs" / "00000000-0000-4000-8000-000000000001"
    artifacts, counters, frontiers, _, _, _ = evaluate_fast_cases(
        config,
        context,
        domain_experiment_id="a" * 64,
        run_directory=run_directory,
        timeout_ms=config.execution.integer_limits.exact_timeout_ms,
        is_cancel_requested=lambda: False,
    )
    assert counters["valid_selections"] > 0
    assert counters["unique_count_requests"] <= counters["valid_selections"]
    assert "d1" in frontiers
    with FastResultReader(
        tmp_path,
        run_directory,
        artifacts,
        completed=True,
    ) as reader:
        first = reader.get_case(0)
    assert first["core_run_id"] is None
    assert first["counting_producer"]["id"] == "linear-forest-closed-form"
    assert first["scientific_status"] == "conclusive"


def test_fast_frontier_matches_reference_with_ties_signs_and_minimization() -> None:
    points = [
        ParetoPoint("a", {"benefit": Fraction(2), "cost": Fraction(-3), "risk": Fraction(1)}),
        ParetoPoint("b", {"benefit": Fraction(2), "cost": Fraction(-3), "risk": Fraction(1)}),
        ParetoPoint("c", {"benefit": Fraction(1), "cost": Fraction(-5), "risk": Fraction(2)}),
        ParetoPoint("d", {"benefit": Fraction(0), "cost": Fraction(1), "risk": Fraction(-1)}),
        ParetoPoint("e", {"benefit": Fraction(3), "cost": Fraction(-2), "risk": Fraction(3)}),
    ]
    directions = {"benefit": "maximize", "cost": "minimize", "risk": "maximize"}
    expected = {
        case_id
        for case_id, (dominated, _) in classify_pareto(points, directions).items()
        if not dominated
    }
    assert classify_fast_frontier(points, directions) == expected


def test_fast_frontier_matches_reference_for_small_exact_grids() -> None:
    for directions in (
        {"a": "maximize"},
        {"a": "maximize", "b": "minimize"},
        {"a": "maximize", "b": "minimize", "c": "maximize"},
    ):
        names = list(directions)
        points = [
            ParetoPoint(
                str(index),
                {name: Fraction(value) for name, value in zip(names, values, strict=True)},
            )
            for index, values in enumerate(product((-1, 0, 1), repeat=len(names)))
        ]
        expected = {
            case_id
            for case_id, (dominated, _) in classify_pareto(points, directions).items()
            if not dominated
        }
        assert classify_fast_frontier(points, directions) == expected


def test_domain_application_completes_fast_run_and_does_not_create_core_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = json.loads(
        Path("examples/domains/single-row-facility-layout/v2-complete.json").read_text(
            encoding="utf-8"
        )
    )
    payload["schema_version"] = "2.1.0"
    payload["domain"]["version"] = "2.1.0"
    payload["execution"]["mode"] = "high_performance"
    core = CoreCommands.open(tmp_path)
    application = DomainApplication(tmp_path, core)
    prepared = application.prepare_payload(json.dumps(payload).encode("utf-8"))
    result = application.run(prepared.domain_experiment_id)
    reopened = application.render(result.manifest.domain_run_id)
    assert application.confirmed_result(result.manifest.domain_run_id) == result.result
    assert result.manifest.status == "completed"
    assert result.manifest.mode == "high_performance"
    assert result.result.execution["mode"] == "high_performance"
    assert reopened.result == result.result
    assert not list((tmp_path / "runs").glob("*"))
    assert (tmp_path / "domain_runs" / result.manifest.domain_run_id / "result.json").is_file()
    objective_ids = [item.definition.id for item in result.result.objective_snapshots]
    if len(objective_ids) >= 2:
        points = application.query_fast_result(
            result.manifest.domain_run_id,
            "plot_points",
            {
                "design_id": result.result.designs[0].design_id,
                "x_objective_id": objective_ids[0],
                "y_objective_id": objective_ids[1],
                "cursor": 0,
            },
        )
        assert points["points"]
        assert all("x" in item and "y" in item for item in points["points"])
        projection_params = {
            "design_id": result.result.designs[0].design_id,
            "x_objective_id": objective_ids[0],
            "y_objective_id": objective_ids[1],
            "x_scale": "automatic",
            "y_scale": "automatic",
            "x_log_k": 100.0,
            "y_log_k": 100.0,
            "level": 0,
            "section": "groups",
            "cursor": 0,
        }
        first_projection_page = application.query_fast_result(
            result.manifest.domain_run_id, "plot_projection", projection_params
        )
        cached_projection = application._fast_result_plot_projection_cache
        second_projection_page = application.query_fast_result(
            result.manifest.domain_run_id,
            "plot_projection",
            {**projection_params, "section": "frontier_positions", "level": 2},
        )
        assert first_projection_page["section"] == "groups"
        assert second_projection_page["section"] == "frontier_positions"
        assert application._fast_result_plot_projection_cache is cached_projection
        reader = application.fast_result_reader(result.manifest)
        application.query_fast_result(
            result.manifest.domain_run_id,
            "case_page",
            {
                "design_id": result.result.designs[0].design_id,
                "order": "case",
                "direction": "ascending",
                "page": 0,
            },
        )
        assert application.fast_result_reader(result.manifest) is reader
        application.close()

    split_workspace = tmp_path / "desktop-flow"
    split_workspace.mkdir()
    split_core = CoreCommands.open(split_workspace)
    split_app = DomainApplication(split_workspace, split_core)
    split_prepared = split_app.prepare_payload(json.dumps(payload).encode("utf-8"))
    reserved = split_app.reserve_grouped_run(split_prepared.domain_experiment_id)
    split_result = split_app.execute_grouped_run(reserved.domain_run_id)
    assert split_result.manifest.status == "completed"

    standard_workspace = tmp_path / "standard"
    standard_workspace.mkdir()
    standard_payload = dict(payload)
    standard_payload["execution"] = dict(payload["execution"])
    standard_payload["execution"]["mode"] = "standard"
    standard_app = DomainApplication(standard_workspace, CoreCommands.open(standard_workspace))
    standard_prepared = standard_app.prepare_payload(json.dumps(standard_payload).encode("utf-8"))
    standard = standard_app.run(standard_prepared.domain_experiment_id).result
    fast_path = tmp_path / "domain_runs" / result.manifest.domain_run_id
    fast_cases: dict[tuple[str, ...], dict[str, object]] = {}
    with FastResultReader(
        tmp_path,
        fast_path,
        result.manifest.fast_artifacts,
        completed=True,
    ) as reader:
        for ordinal in range(reader.case_count):
            case = reader.get_case(ordinal)
            fast_cases[tuple(case["added_component_ids"])] = case
    standard_cases = {tuple(case.added_component_ids): case for case in standard.designs[0].cases}
    assert set(fast_cases) == set(standard_cases)
    for selection, fast_case in fast_cases.items():
        standard_case = standard_cases[selection]
        assert int(fast_case["compatible_layout_count"]["value"]) == int(
            standard_case.compatible_layout_count.value
        )
        assert fast_case["criteria_vector"] == {
            key: {
                "numerator": value.numerator,
                "denominator": value.denominator,
            }
            for key, value in standard_case.criteria_vector.items()
        }
    if len(objective_ids) >= 2:

        def page_with_missing_x(
            _reader: FastResultReader,
            _order_path: str,
            _page: int,
            *,
            page_size: int = 50,
            reverse: bool = False,
        ) -> list[dict[str, object]]:
            assert page_size == 50 and not reverse
            return [
                {
                    "case_id": "case-with-missing-x",
                    "criteria_vector": {objective_ids[1]: {"numerator": 3, "denominator": 2}},
                }
            ]

        with monkeypatch.context() as patch:
            patch.setattr(FastResultReader, "page", page_with_missing_x)
            partial = application.query_fast_result(
                result.manifest.domain_run_id,
                "plot_points",
                {
                    "design_id": result.result.designs[0].design_id,
                    "x_objective_id": objective_ids[0],
                    "y_objective_id": objective_ids[1],
                    "cursor": 0,
                },
            )
        assert partial["points"] == [
            {
                "case_id": "case-with-missing-x",
                "x": None,
                "y": {"numerator": 3, "denominator": 2},
            }
        ]


def test_cancelled_fast_run_is_terminal_without_confirmed_result(tmp_path: Path) -> None:
    payload = json.loads(
        Path("examples/domains/single-row-facility-layout/v2-complete.json").read_text(
            encoding="utf-8"
        )
    )
    payload["schema_version"] = "2.1.0"
    payload["domain"]["version"] = "2.1.0"
    payload["execution"]["mode"] = "high_performance"
    core = CoreCommands.open(tmp_path)
    application = DomainApplication(tmp_path, core, is_cancel_requested=lambda: True)
    prepared = application.prepare_payload(json.dumps(payload).encode("utf-8"))
    with pytest.raises(DomainRunCancelled) as cancelled:
        application.run(prepared.domain_experiment_id)
    run_id = cancelled.value.manifest.domain_run_id
    manifest, _ = application.store.load_domain_run(run_id)
    assert manifest.status == "cancelled"
    assert not (tmp_path / "domain_runs" / run_id / "result.json").exists()


def test_failed_fast_run_keeps_terminal_manifest_without_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.loads(
        Path("examples/domains/single-row-facility-layout/v2-complete.json").read_text(
            encoding="utf-8"
        )
    )
    payload["schema_version"] = "2.1.0"
    payload["domain"]["version"] = "2.1.0"
    payload["execution"]["mode"] = "high_performance"

    def fail_fast_pass(*_: object, **__: object) -> None:
        raise RuntimeError("injected failure")

    monkeypatch.setattr(fast_execution_module, "evaluate_fast_cases", fail_fast_pass)
    core = CoreCommands.open(tmp_path)
    application = DomainApplication(tmp_path, core)
    prepared = application.prepare_payload(json.dumps(payload).encode("utf-8"))
    with pytest.raises(DomainExtensionError, match="falló; no hay resultado confirmado"):
        application.run(prepared.domain_experiment_id)
    manifests = application.store.list_domain_runs()
    manifest = manifests[0][0]
    assert manifest.status == "failed"
    assert not (tmp_path / "domain_runs" / manifest.domain_run_id / "result.json").exists()


def test_gateway_startup_marks_interrupted_fast_runs_failed(tmp_path: Path) -> None:
    payload = json.loads(
        Path("examples/domains/single-row-facility-layout/v2-complete.json").read_text(
            encoding="utf-8"
        )
    )
    payload["schema_version"] = "2.1.0"
    payload["domain"]["version"] = "2.1.0"
    payload["execution"]["mode"] = "high_performance"
    application = DomainApplication(tmp_path, CoreCommands.open(tmp_path))
    prepared = application.prepare_payload(json.dumps(payload).encode("utf-8"))
    reserved = application.reserve_grouped_run(prepared.domain_experiment_id)
    running = reserved.model_copy(
        update={"status": "running", "active_started_at": application.store.clock()}
    )
    application.store.write_domain_run(running)

    assert application.fail_interrupted_high_performance_runs() == 1
    recovered, _ = application.store.load_domain_run(reserved.domain_run_id)
    assert recovered.status == "failed"
    assert recovered.failure_reason == "interrupted"
    assert not (tmp_path / "domain_runs" / reserved.domain_run_id / "result.json").exists()
