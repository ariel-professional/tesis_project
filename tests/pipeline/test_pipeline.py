from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

import tesis_proyect.pipeline.orchestrator as orchestrator_module
from tesis_proyect.application.experiments import ExperimentService
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import AttemptMetrics, ProducerRef, StructuredError
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import STAGE_ORDER, ErrorCode, RunStatus, StageId, StageStatus
from tesis_proyect.models.execution import PipelineState
from tesis_proyect.models.reports import ReportSummary
from tesis_proyect.models.scientific import ComparisonResult
from tesis_proyect.models.stages import StageResult
from tesis_proyect.persistence.json_store import JsonStore
from tesis_proyect.persistence.workspace import Workspace
from tesis_proyect.pipeline.orchestrator import PipelineCoordinator
from tests.contracts.test_foundation import valid_config

pytestmark = pytest.mark.integration

RUN_ID = UUID("12345678-1234-4234-8234-123456789abc")


def create_run(tmp_path: Path, config: ExperimentConfig) -> tuple[Workspace, str]:
    workspace = Workspace.open(tmp_path)
    service = ExperimentService(
        workspace,
        uuid_factory=lambda: RUN_ID,
        clock=lambda: "2026-08-05T15:30:00.000Z",
    )
    service.save_experiment("baseline", config)
    return workspace, service.create_run("baseline").run_id


def stage_path(tmp_path: Path, run_id: str, ordinal: int, stage: str) -> Path:
    return tmp_path / "runs" / run_id / "stages" / f"{ordinal:02d}_{stage}.json"


def test_complete_pipeline_with_exact_closed_form(tmp_path: Path) -> None:
    data = valid_config()
    data["source"] = {"kind": "inline", "edges": [[1, 2]]}
    workspace, run_id = create_run(tmp_path, ExperimentConfig.model_validate(data))
    manifest = PipelineCoordinator(
        workspace, run_id, clock=lambda: "2026-08-05T15:30:00.000Z"
    ).run()
    assert manifest.status == RunStatus.COMPLETED
    root = tmp_path / "runs" / run_id
    assert not (root / "artifacts" / "instance_candidate.json").exists()
    for ordinal, stage in enumerate(STAGE_ORDER, start=1):
        assert stage_path(tmp_path, run_id, ordinal, stage).is_file()
    store = JsonStore(workspace)
    pipeline = store.read_model(f"runs/{run_id}/pipeline.json", PipelineState, max_bytes=1_000_000)
    assert [state.status for state in pipeline.ordered_stages] == [
        StageStatus.SUCCESS,
        StageStatus.SUCCESS,
        StageStatus.SUCCESS,
        StageStatus.SUCCESS,
        StageStatus.SUCCESS,
        StageStatus.SUCCESS,
        StageStatus.SUCCESS,
        StageStatus.SUCCESS,
        StageStatus.SUCCESS,
        StageStatus.SUCCESS,
    ]
    comparison = store.read_model(
        f"runs/{run_id}/artifacts/comparison_result.json",
        ComparisonResult,
        max_bytes=1_000_000,
    )
    assert comparison.status == "match"
    assert comparison.value_exact == comparison.value_reference == 6
    report = store.read_model(
        f"runs/{run_id}/reports/result.json", ReportSummary, max_bytes=1_000_000
    )
    assert report.run_status == RunStatus.COMPLETED
    assert report.methods.reference is not None
    assert report.methods.reference.value == 6
    markdown = (root / "reports" / "report.md").read_text(encoding="utf-8")
    assert markdown.startswith("# Experiment result\n")


@pytest.mark.parametrize(
    ("edges", "failed_ordinal", "forbidden"),
    [
        ([[1, 1]], 3, ["instance.json", "structure_summary.json", "reference_result.json"]),
        (
            [[1, 2], [2, 3], [1, 3]],
            4,
            ["structure_summary.json", "reference_result.json"],
        ),
    ],
)
def test_invalid_pipeline_preserves_only_contract_evidence(
    tmp_path: Path, edges: list[list[int]], failed_ordinal: int, forbidden: list[str]
) -> None:
    data = valid_config()
    data["source"] = {"kind": "inline", "edges": edges}
    workspace, run_id = create_run(tmp_path, ExperimentConfig.model_validate(data))
    manifest = PipelineCoordinator(
        workspace, run_id, clock=lambda: "2026-08-05T15:30:00.000Z"
    ).run()
    assert manifest.status == RunStatus.FAILED
    root = tmp_path / "runs" / run_id
    assert (root / "reports" / "result.json").is_file()
    for name in forbidden:
        assert not (root / "artifacts" / name).exists()
    store = JsonStore(workspace)
    failed_stage = STAGE_ORDER[failed_ordinal - 1]
    result = store.read_model(
        f"runs/{run_id}/stages/{failed_ordinal:02d}_{failed_stage}.json",
        StageResult,
        max_bytes=1_000_000,
    )
    assert result.status == "failed"
    assert result.outcome is not None
    pipeline = store.read_model(f"runs/{run_id}/pipeline.json", PipelineState, max_bytes=1_000_000)
    assert pipeline.ordered_stages[8].status == StageStatus.SUCCESS
    assert pipeline.ordered_stages[9].status == StageStatus.SUCCESS


def test_stage_two_file_failure_skips_all_dependents_but_reports(tmp_path: Path) -> None:
    data = valid_config()
    data["source"] = {"kind": "file", "path": "missing.json"}
    workspace, run_id = create_run(tmp_path, ExperimentConfig.model_validate(data))
    manifest = PipelineCoordinator(
        workspace, run_id, clock=lambda: "2026-08-05T15:30:00.000Z"
    ).run()
    assert manifest.status == RunStatus.FAILED
    pipeline = JsonStore(workspace).read_model(
        f"runs/{run_id}/pipeline.json", PipelineState, max_bytes=1_000_000
    )
    assert pipeline.ordered_stages[1].status == StageStatus.FAILED
    assert all(state.status == StageStatus.SKIPPED for state in pipeline.ordered_stages[2:8])
    assert all(state.status == StageStatus.SUCCESS for state in pipeline.ordered_stages[8:])


def test_persisted_report_is_a_derived_view(tmp_path: Path) -> None:
    data = valid_config()
    data["source"] = {"kind": "inline", "edges": []}
    workspace, run_id = create_run(tmp_path, ExperimentConfig.model_validate(data))
    PipelineCoordinator(workspace, run_id, clock=lambda: "2026-08-05T15:30:00.000Z").run()
    report = JsonStore(workspace).read_model(
        f"runs/{run_id}/reports/result.json", ReportSummary, max_bytes=1_000_000
    )
    assert report.methods.reference is not None
    assert report.methods.reference.value == 12


def prepared_runner(tmp_path: Path) -> PipelineCoordinator:
    data = valid_config()
    data["source"] = {"kind": "inline", "edges": [[1, 2]]}
    workspace, run_id = create_run(tmp_path, ExperimentConfig.model_validate(data))
    runner = PipelineCoordinator(workspace, run_id)
    runner.handlers.define()
    runner.handlers.candidate()
    assert runner.handlers.edges() is None
    assert runner.handlers.forest() is None
    runner.handlers.analysis()
    return runner


@pytest.mark.parametrize("code", [ErrorCode.STAGE_TIMEOUT, ErrorCode.RUN_CANCELLED])
def test_count_stage_commits_worker_transport_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: ErrorCode
) -> None:
    runner = prepared_runner(tmp_path)

    def fail(*args: object, **kwargs: object) -> object:
        raise OperationalError(code, "Injected worker failure.")

    monkeypatch.setattr(orchestrator_module, "execute_worker", fail)
    returned = runner.handlers.count(
        StageId.RUN_EXACT_METHOD, ProducerRef(id="exact", version="1"), "exact_result.json"
    )
    assert returned == code
    expected = "cancelled" if code == ErrorCode.RUN_CANCELLED else "failed"
    assert runner.results[StageId.RUN_EXACT_METHOD].status == expected


@pytest.mark.parametrize("with_error", [False, True])
def test_count_stage_rejects_failed_worker_responses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, with_error: bool
) -> None:
    runner = prepared_runner(tmp_path)
    error = (
        StructuredError(
            schema_version="1.0.0",
            code=ErrorCode.RUN_CANCELLED,
            domain_error_code=10,
            message="Cancelled.",
            recoverable=False,
            details={},
            stage=StageId.RUN_EXACT_METHOD,
        )
        if with_error
        else None
    )
    metrics = AttemptMetrics(
        duration_ms=0,
        worker_duration_ms=0,
        candidates_examined=None,
        peak_memory_bytes=None,
        producer=ProducerRef(id="exact", version="1"),
    )
    response = SimpleNamespace(status="failed", result=None, error=error, metrics=metrics)
    monkeypatch.setattr(
        orchestrator_module, "execute_worker", lambda *args, **kwargs: (response, "cooperative")
    )
    returned = runner.handlers.count(
        StageId.RUN_EXACT_METHOD, ProducerRef(id="exact", version="1"), "exact_result.json"
    )
    assert returned == (ErrorCode.RUN_CANCELLED if with_error else ErrorCode.WORKER_PROTOCOL_ERROR)
