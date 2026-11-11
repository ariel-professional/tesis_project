from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tesis_domain_extensions.application import DomainApplication
from tesis_domain_extensions.contracts.common import CoreRunAttempt
from tesis_domain_extensions.domains.inspection_route.adapter import InspectionRouteAdapter
from tesis_domain_extensions.domains.inspection_route.generation import (
    InspectionScenarioGenerator,
)
from tesis_domain_extensions.domains.single_row_facility_layout.adapter import (
    SingleRowFacilityLayoutAdapter,
)
from tesis_domain_extensions.domains.single_row_facility_layout.generation import (
    LinearForestGenerator,
)
from tesis_domain_extensions.errors import DomainExtensionError, DomainRunCancelled
from tesis_proyect.application.commands import CoreCommands
from tesis_proyect.models.common import AttemptMetrics, StructuredError
from tesis_proyect.models.enums import DOMAIN_ERROR_CODES, ErrorCode, StageId, StageStatus
from tesis_proyect.models.execution import StageAttempt
from tesis_proyect.models.protocols import StageInspection
from tesis_proyect.models.stages import StageResult


def test_payload_api_validates_estimates_and_prepares_without_a_draft_file(
    tmp_path: Path,
) -> None:
    payload = Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    application = DomainApplication(tmp_path, CoreCommands.open(tmp_path))

    validated = application.validate_payload(payload)
    estimate = application.estimate_payload(payload)
    prepared = application.prepare_payload(payload)

    assert validated.model_dump()["domain"]["id"] == "single-row-facility-layout"
    assert estimate > 0
    assert prepared.domain.id == "single-row-facility-layout"
    assert application.cancel_active_core() is None


def test_both_generators_stop_at_domain_owned_checkpoints() -> None:
    inspection_adapter = InspectionRouteAdapter()
    inspection_config = inspection_adapter.parse_config(
        Path("examples/domains/inspection-route/comparison.json").read_bytes()
    )
    inspection_context = inspection_adapter.project(inspection_config).context
    inspection = InspectionScenarioGenerator(
        inspection_config,
        inspection_context,
        is_cancel_requested=lambda: True,
    )
    with pytest.raises(DomainRunCancelled):
        next(iter(inspection))

    layout_adapter = SingleRowFacilityLayoutAdapter()
    layout_config = layout_adapter.parse_config(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    layout_context = layout_adapter.project(layout_config).context
    layout = LinearForestGenerator(
        layout_config,
        layout_context,
        is_cancel_requested=lambda: True,
    )
    with pytest.raises(DomainRunCancelled):
        next(iter(layout))


@pytest.mark.integration
def test_cancel_during_generation_does_not_create_another_core_case(tmp_path: Path) -> None:
    core = CoreCommands.open(tmp_path)
    prepared = DomainApplication(tmp_path, core).prepare(
        Path("examples/domains/single-row-facility-layout/comparison.json")
    )
    application = DomainApplication(
        tmp_path,
        core,
        is_cancel_requested=lambda: bool(core.list_runs().runs),
    )

    with pytest.raises(DomainRunCancelled) as cancelled:
        application.run(prepared.reference)
    manifest = cancelled.value.manifest

    assert manifest is not None
    assert manifest.status == "cancelled"
    assert len(manifest.cases) == 1
    assert manifest.cases[0].status == "cancelled"
    assert len(core.list_runs().runs) == 1


@pytest.mark.integration
def test_cancelled_resume_keeps_the_new_core_attempt_in_the_group_manifest(
    tmp_path: Path,
) -> None:
    core = CoreCommands.open(tmp_path)
    setup = DomainApplication(tmp_path, core)
    prepared = setup.prepare(Path("examples/domains/single-row-facility-layout/comparison.json"))
    manifest = setup.reserve_grouped_run(prepared.reference)
    loaded = setup.store.resolve(prepared.reference)
    case = next(
        iter(
            loaded.adapter.generate_cases(
                loaded.record.domain_config,
                loaded.record.projection_context,
            ).cases
        )
    )
    setup._ensure_core_experiment(case)
    first = core.create_run(case.core_experiment_id)
    core.cancel(first.run_id)
    persisted = loaded.adapter.build_persisted_case(case, core_run_id=first.run_id)
    persisted = persisted.model_copy(
        update={"attempts": [CoreRunAttempt(core_run_id=first.run_id, status="cancelled")]}
    )
    manifest = manifest.model_copy(
        update={"cases": [persisted], "generator_cursor": 1, "status": "cancelled"}
    )
    setup.store.write_domain_run(manifest)

    application = DomainApplication(
        tmp_path,
        core,
        is_cancel_requested=lambda: len(core.list_runs().runs) > 1,
    )
    with pytest.raises(DomainRunCancelled) as cancelled:
        application.resume(manifest.domain_run_id)

    current = cancelled.value.manifest
    assert current is not None
    assert current.status == "cancelled"
    assert len(current.cases[0].attempts) == 2
    assert current.cases[0].attempts[0].core_run_id == first.run_id
    assert current.cases[0].attempts[1].core_run_id != first.run_id
    assert current.cases[0].attempts[1].status == "cancelled"


@pytest.mark.integration
def test_resume_replaces_a_cancelled_core_attempt_and_preserves_history(
    tmp_path: Path,
) -> None:
    core = CoreCommands.open(tmp_path)
    application = DomainApplication(tmp_path, core)
    prepared = application.prepare(
        Path("examples/domains/single-row-facility-layout/comparison.json")
    )
    manifest = application.reserve_grouped_run(prepared.reference)
    loaded = application.store.resolve(prepared.reference)
    case = next(
        loaded.adapter.generate_cases(
            loaded.record.domain_config,
            loaded.record.projection_context,
        ).cases
    )
    application._ensure_core_experiment(case)
    cancelled = core.create_run(case.core_experiment_id)
    core.cancel(cancelled.run_id)
    persisted = loaded.adapter.build_persisted_case(case, core_run_id=cancelled.run_id)
    persisted = persisted.model_copy(
        update={"attempts": [CoreRunAttempt(core_run_id=cancelled.run_id, status="cancelled")]}
    )
    manifest = manifest.model_copy(
        update={"cases": [persisted], "generator_cursor": 1, "status": "cancelled"}
    )
    application.store.write_domain_run(manifest)

    resumed = application.resume(manifest.domain_run_id)
    current, _ = application.store.load_domain_run(manifest.domain_run_id)

    assert resumed.manifest.status == "completed"
    assert len(current.cases[0].attempts) == 2
    assert current.cases[0].attempts[0].core_run_id == cancelled.run_id
    assert current.cases[0].attempts[0].status == "cancelled"
    assert current.cases[0].attempts[1].core_run_id != cancelled.run_id
    assert current.cases[0].attempts[1].status == "completed"
    persisted_payload = current.cases[0].model_dump(mode="json")
    assert "core_run_id" not in persisted_payload
    assert "status" not in persisted_payload


def test_grouped_run_stops_at_the_first_failed_core_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = CoreCommands.open(tmp_path)
    application = DomainApplication(tmp_path, core)
    prepared = application.prepare(
        Path("examples/domains/single-row-facility-layout/comparison.json")
    )
    original_create_run = core.create_run
    created_runs: list[str] = []

    def create_run(experiment_id: str):
        manifest = original_create_run(experiment_id)
        created_runs.append(manifest.run_id)
        return manifest

    def failed_inspection(run_id: str):
        return SimpleNamespace(
            run=SimpleNamespace(
                run_id=run_id,
                status=SimpleNamespace(value="failed"),
            ),
            pipeline=SimpleNamespace(
                ordered_stages=[
                    SimpleNamespace(
                        stage=StageId.RUN_REFERENCE_METHOD,
                        status=StageStatus.FAILED,
                    )
                ]
            ),
        )

    def failed_stage_inspection(run_id: str, *, stage: StageId) -> StageInspection:
        error = StructuredError(
            schema_version="1.0.0",
            code=ErrorCode.STAGE_TIMEOUT,
            domain_error_code=DOMAIN_ERROR_CODES[ErrorCode.STAGE_TIMEOUT],
            message="worker timed out",
            recoverable=False,
            details={},
            stage=stage,
        )
        timestamp = "2026-09-03T00:00:00.000Z"
        result = StageResult(
            schema_version="1.0.0",
            stage=stage,
            status="failed",
            attempts=[
                StageAttempt(
                    number=1,
                    started_at=timestamp,
                    finished_at=timestamp,
                    duration_ms=0,
                    status="failed",
                    error=error,
                    skip=None,
                    metrics=AttemptMetrics(
                        duration_ms=0,
                        worker_duration_ms=None,
                        candidates_examined=None,
                        peak_memory_bytes=None,
                        producer=None,
                    ),
                    termination="not_applicable",
                )
            ],
            started_at=timestamp,
            finished_at=timestamp,
            duration_ms=0,
            error=error,
            artifacts=[],
            outcome=None,
        )
        return StageInspection(
            schema_version="1.0.0",
            view="stage",
            run_id=run_id,
            stage=stage,
            result=result,
        )

    monkeypatch.setattr(core, "create_run", create_run)
    monkeypatch.setattr(
        core,
        "run",
        lambda run_id: SimpleNamespace(
            run_id=run_id,
            status=SimpleNamespace(value="failed"),
        ),
    )
    monkeypatch.setattr(core, "inspect_run", failed_inspection)
    monkeypatch.setattr(
        core,
        "inspect",
        failed_stage_inspection,
    )

    with pytest.raises(DomainExtensionError, match="STAGE_TIMEOUT"):
        application.run(prepared.reference)

    manifests = [manifest for manifest, _adapter in application.store.list_domain_runs()]
    assert len(manifests) == 1
    manifest = manifests[0]
    assert manifest.status == "failed"
    assert len(manifest.cases) == 1
    assert manifest.cases[0].attempts[-1].status == "failed"
    assert len(created_runs) == 1
