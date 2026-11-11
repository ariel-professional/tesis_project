from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from tesis_domain_extensions.application import DomainApplication
from tesis_domain_extensions.domains.inspection_route.adapter import InspectionRouteAdapter
from tesis_domain_extensions.domains.inspection_route.contracts import InspectionRouteConfig
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_domain_extensions.projection_store import ProjectionStore
from tesis_proyect.application.commands import CoreCommands
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode

pytestmark = pytest.mark.integration


def test_prepare_persists_an_autonomous_grouped_projection_without_core_experiment(
    tmp_path: Path,
    partial_config: InspectionRouteConfig,
) -> None:
    (tmp_path / "experiments").mkdir()
    (tmp_path / "runs").mkdir()
    store = ProjectionStore(tmp_path, CoreCommands.open(tmp_path))
    loaded = store.prepare(InspectionRouteAdapter(), partial_config)
    experiment_id = loaded.record.domain_experiment_id
    assert not (tmp_path / "experiments" / f"{experiment_id}.json").exists()
    assert list((tmp_path / "experiments").iterdir()) == []
    assert (tmp_path / "domain_projections" / f"{experiment_id}.json").is_file()
    assert loaded.record.domain_config == partial_config
    assert set(loaded.record.projection_context.model_dump(mode="json")) == {
        "schema_version",
        "vertex_mapping",
    }


def test_grouped_domain_execution_creates_child_runs_without_domain_files(
    tmp_path: Path,
    partial_config: InspectionRouteConfig,
) -> None:
    (tmp_path / "experiments").mkdir()
    (tmp_path / "runs").mkdir()
    core = CoreCommands.open(tmp_path)
    loaded = ProjectionStore(tmp_path, core).prepare(InspectionRouteAdapter(), partial_config)
    result = DomainApplication(tmp_path, core).run(loaded.record.domain_experiment_id[:8])
    assert result.result.generation.core_cases == 3
    manifest, _ = ProjectionStore(tmp_path, core).load_domain_run(result.manifest.domain_run_id[:8])
    for child in manifest.cases:
        info = core.inspect_run(child.core_run_id).run
        assert info.experiment_id == child.core_experiment_id
        run_files = {path.name for path in (tmp_path / "runs" / child.core_run_id).iterdir()}
        assert "domain_config.json" not in run_files
        assert "projection.json" not in run_files


def test_equal_inspection_policies_keep_scenarios_and_share_one_core_run(
    tmp_path: Path,
    partial_config: InspectionRouteConfig,
) -> None:
    payload = partial_config.model_dump(mode="python")
    payload["study"]["scenarios"][1]["required_consecutive_visits"] = deepcopy(
        payload["study"]["scenarios"][0]["required_consecutive_visits"]
    )
    config = InspectionRouteConfig.model_validate(payload)
    core = CoreCommands.open(tmp_path)
    loaded = ProjectionStore(tmp_path, core).prepare(InspectionRouteAdapter(), config)

    interpreted = DomainApplication(tmp_path, core).run(loaded.record.domain_experiment_id[:8])
    result = interpreted.result
    manifest = interpreted.manifest

    assert result.generation.duplicate_constraint_sets == 1
    assert result.generation.core_cases == 2
    assert len(manifest.cases) == 2
    first, second = result.scenarios[:2]
    assert first.scenario_id != second.scenario_id
    assert first.constraint_set_id == second.constraint_set_id
    assert first.core_run_id == second.core_run_id
    assert result.most_flexible_scenario_ids == [first.scenario_id, second.scenario_id]


def test_srfl_v2_integral_study_executes_persists_and_reopens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = CoreCommands.open(tmp_path)
    application = DomainApplication(tmp_path, core)
    definition = Path("examples/domains/single-row-facility-layout/v2-complete.json")

    prepared = application.prepare(definition)
    interpreted = application.run(prepared.reference)
    reopened = application.render(interpreted.manifest.domain_run_id)

    result_path = tmp_path / "domain_runs" / interpreted.manifest.domain_run_id / "result.json"
    confirmed_bytes = result_path.read_bytes()

    def unexpected_export(_run_id: str) -> None:
        pytest.fail("opening a confirmed result must not export CORE evidence again")

    monkeypatch.setattr(core, "export", unexpected_export)
    confirmed = application.confirmed_result(interpreted.manifest.domain_run_id)
    assert confirmed == reopened.result
    assert result_path.read_bytes() == confirmed_bytes

    result_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DomainExtensionError, match="resultado confirmado del dominio es inválido"):
        application.confirmed_result(interpreted.manifest.domain_run_id)
    result_path.write_bytes(confirmed_bytes)

    mismatched = confirmed.model_copy(
        update={
            "execution": {
                **confirmed.execution,
                "domain_run_id": "00000000-0000-4000-8000-000000000000",
            }
        }
    )
    original_result_loader = application.store.load_domain_result_document
    monkeypatch.setattr(
        application.store,
        "load_domain_result_document",
        lambda *_args: (mismatched, confirmed_bytes),
    )
    with pytest.raises(DomainExtensionError, match="no corresponde a la ejecución"):
        application.confirmed_result(interpreted.manifest.domain_run_id)
    monkeypatch.setattr(application.store, "load_domain_result_document", original_result_loader)

    original_run_loader = application.store.load_domain_run

    def load_running_manifest(reference: str):
        manifest, adapter = original_run_loader(reference)
        return manifest.model_copy(update={"status": "running"}), adapter

    monkeypatch.setattr(application.store, "load_domain_run", load_running_manifest)
    with pytest.raises(DomainExtensionError, match="todavía no tiene un resultado confirmado"):
        application.confirmed_result(interpreted.manifest.domain_run_id)
    monkeypatch.setattr(application.store, "load_domain_run", original_run_loader)

    result = reopened.result
    assert result.schema_version == "2.0.0"
    assert result.generation.valid_selections == 2
    assert result.generation.forbidden_combinations == 2
    assert result.designs[0].invalid_combination_count == 2
    assert len(result.designs[0].pareto_case_ids) == 2
    warned = next(case for case in result.designs[0].cases if case.findings)
    assert warned.captured_flow is None
    assert [
        (item.matrix_id, str(item.total), item.direction) for item in warned.adjacency_values
    ] == [
        ("movimientos", "150", "maximize"),
        ("riesgo-operativo", "6.5", "minimize"),
    ]
    assert warned.findings[0].policy == "warn"


def test_all_invalid_inspection_study_is_not_applicable_and_never_runs_core(
    tmp_path: Path,
    partial_config: InspectionRouteConfig,
) -> None:
    payload = partial_config.model_dump(mode="python")
    invalid = deepcopy(payload["study"]["scenarios"][-1])
    payload["study"]["scenarios"] = [
        invalid,
        {**deepcopy(invalid), "id": "otra-politica-imposible"},
    ]
    config = InspectionRouteConfig.model_validate(payload)
    core = CoreCommands.open(tmp_path)
    loaded = ProjectionStore(tmp_path, core).prepare(InspectionRouteAdapter(), config)

    interpreted = DomainApplication(tmp_path, core).run(loaded.record.domain_experiment_id[:8])

    assert interpreted.result.comparison_status == "not_applicable"
    assert interpreted.result.most_flexible_scenario_ids == []
    assert interpreted.result.generation.core_cases == 0
    assert interpreted.manifest.cases == []
    assert not (tmp_path / "experiments").exists()


def test_projection_listing_filters_domain_and_prefix(
    tmp_path: Path,
    partial_config: InspectionRouteConfig,
) -> None:
    (tmp_path / "experiments").mkdir()
    (tmp_path / "runs").mkdir()
    store = ProjectionStore(tmp_path, CoreCommands.open(tmp_path))
    loaded = store.prepare(InspectionRouteAdapter(), partial_config)
    experiment_id = loaded.record.domain_experiment_id
    assert len(store.list_experiments(domain_id="inspection-route", prefix=None).experiments) == 1
    assert len(store.list_experiments(domain_id="other", prefix=None).experiments) == 0
    assert len(store.list_experiments(domain_id=None, prefix=experiment_id[:1]).experiments) == 1


def test_domain_run_failure_preserves_the_created_run_and_resume_command(
    tmp_path: Path,
    example_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = CoreCommands.open(tmp_path)
    application = DomainApplication(tmp_path, core)
    prepared = application.prepare(example_root / "comparison.json")

    def fail_after_creation(reference: str):
        raise OperationalError(ErrorCode.IO_ERROR, reference)

    monkeypatch.setattr(core, "run", fail_after_creation)
    with pytest.raises(DomainExtensionError, match="tesis-domain resume") as failure:
        application.run(prepared.reference)
    assert failure.value.exit_code == 74
    domain_runs = application.store.list_domain_runs()
    assert len(domain_runs) == 1
    assert len(domain_runs[0][0].cases) == 1
