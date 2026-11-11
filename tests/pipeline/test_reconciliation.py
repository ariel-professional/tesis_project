from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tesis_proyect.application.operations import RunOperations
from tesis_proyect.cli.event_adapter import PublicEventObserver
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import STAGE_ORDER, ErrorCode, RunStatus, StageId, StageStatus
from tesis_proyect.models.execution import PipelineState
from tesis_proyect.models.reports import ReportSummary
from tesis_proyect.models.stages import MetricsOutcome, StageResult
from tesis_proyect.persistence.json_store import JsonStore
from tests.contracts.test_foundation import valid_config
from tests.pipeline.test_pipeline import create_run

pytestmark = pytest.mark.integration


def _complete(tmp_path: Path) -> tuple[Any, str, JsonStore]:
    data = valid_config()
    data["source"] = {"kind": "inline", "edges": [[1, 2]]}
    workspace, run_id = create_run(tmp_path, ExperimentConfig.model_validate(data))
    assert RunOperations(workspace).run(run_id).status == RunStatus.COMPLETED
    return workspace, run_id, JsonStore(workspace)


def _stage_bytes(tmp_path: Path, run_id: str, through: int = 10) -> list[bytes]:
    root = tmp_path / "runs" / run_id / "stages"
    return [
        (root / f"{index:02d}_{stage.value}.json").read_bytes()
        for index, stage in enumerate(STAGE_ORDER[:through], start=1)
    ]


def test_stage_result_ahead_repairs_pipeline_without_recomputation(tmp_path: Path) -> None:
    workspace, run_id, store = _complete(tmp_path)
    before = _stage_bytes(tmp_path, run_id)
    pipeline = store.read_model(f"runs/{run_id}/pipeline.json", PipelineState, max_bytes=1_000_000)
    last = pipeline.ordered_stages[-1]
    pipeline.ordered_stages[-1] = last.model_copy(
        update={"status": StageStatus.PENDING, "attempt_count": 0, "result": None}
    )
    store.write_json(f"runs/{run_id}/pipeline.json", pipeline)

    assert RunOperations(workspace).resume(run_id).status == RunStatus.COMPLETED
    repaired = store.read_model(f"runs/{run_id}/pipeline.json", PipelineState, max_bytes=1_000_000)
    assert repaired.ordered_stages[-1].status == StageStatus.SUCCESS
    assert repaired.ordered_stages[-1].attempt_count == 1
    assert _stage_bytes(tmp_path, run_id) == before


def test_pipeline_ahead_of_missing_stage_recomputes_only_that_stage(tmp_path: Path) -> None:
    workspace, run_id, store = _complete(tmp_path)
    before = _stage_bytes(tmp_path, run_id, through=9)
    (tmp_path / "runs" / run_id / "stages" / "10_export_report.json").unlink()

    assert RunOperations(workspace).resume(run_id).status == RunStatus.COMPLETED
    assert _stage_bytes(tmp_path, run_id, through=9) == before
    stage = store.read_model(
        f"runs/{run_id}/stages/10_export_report.json", StageResult, max_bytes=1_000_000
    )
    assert len(stage.attempts) == 1


def test_corrupt_report_recomputes_only_stage_ten_and_preserves_attempt(tmp_path: Path) -> None:
    workspace, run_id, store = _complete(tmp_path)
    before = _stage_bytes(tmp_path, run_id, through=9)
    report_path = tmp_path / "runs" / run_id / "reports" / "report.md"
    report_path.write_text("corrupt\n", encoding="utf-8")

    assert RunOperations(workspace).resume(run_id).status == RunStatus.COMPLETED
    assert _stage_bytes(tmp_path, run_id, through=9) == before
    stage = store.read_model(
        f"runs/{run_id}/stages/10_export_report.json", StageResult, max_bytes=1_000_000
    )
    assert [attempt.number for attempt in stage.attempts] == [1, 2]
    assert report_path.read_text(encoding="utf-8").startswith("# Experiment result\n")


def test_corrupt_instance_rolls_back_to_candidate_and_updates_last_attempt_metrics(
    tmp_path: Path,
) -> None:
    workspace, run_id, store = _complete(tmp_path)
    stage_one = _stage_bytes(tmp_path, run_id, through=1)
    instance = tmp_path / "runs" / run_id / "artifacts" / "instance.json"
    instance.write_text("{}\n", encoding="utf-8")

    assert RunOperations(workspace).resume(run_id).status == RunStatus.COMPLETED
    assert _stage_bytes(tmp_path, run_id, through=1) == stage_one
    for ordinal, stage_id in enumerate(STAGE_ORDER[1:], start=2):
        stage = store.read_model(
            f"runs/{run_id}/stages/{ordinal:02d}_{stage_id.value}.json",
            StageResult,
            max_bytes=1_000_000,
        )
        assert [attempt.number for attempt in stage.attempts] == [1, 2]
    metrics = store.read_model(
        f"runs/{run_id}/stages/09_collect_metrics.json",
        StageResult,
        max_bytes=1_000_000,
    )
    assert isinstance(metrics.outcome, MetricsOutcome)
    assert [item.attempt_number for item in metrics.outcome.stages] == [1, 2, 2, 2, 2, 2, 2, 2]
    report = store.read_model(
        f"runs/{run_id}/reports/result.json", ReportSummary, max_bytes=1_000_000
    )
    assert report.metrics == metrics.outcome.stages


def test_corrupt_stage_history_starts_recoverable_history_and_emits_diagnostic(
    tmp_path: Path,
) -> None:
    workspace, run_id, store = _complete(tmp_path)
    path = tmp_path / "runs" / run_id / "stages" / "05_analyze_structure.json"
    path.write_text("not-json\n", encoding="utf-8")
    events = []

    assert (
        RunOperations(workspace, observer=PublicEventObserver(events.append)).resume(run_id).status
        == RunStatus.COMPLETED
    )
    diagnostic = next(item for item in events if item.event == "diagnostic")
    assert diagnostic.payload.error.code == ErrorCode.INTEGRITY_ERROR
    assert diagnostic.payload.error.stage == StageId.ANALYZE_STRUCTURE
    stage = store.read_model(
        f"runs/{run_id}/stages/05_analyze_structure.json",
        StageResult,
        max_bytes=1_000_000,
    )
    assert [attempt.number for attempt in stage.attempts] == [1]


def test_resume_blocks_valid_but_hash_incompatible_configuration(tmp_path: Path) -> None:
    workspace, run_id, store = _complete(tmp_path)
    relative = f"runs/{run_id}/config/run_config.json"
    config = store.read_json_value(relative, max_bytes=1_000_000)
    config["n"] = 5
    store.write_json(relative, config)
    with pytest.raises(OperationalError) as failure:
        RunOperations(workspace).resume(run_id)
    assert failure.value.code == ErrorCode.INTEGRITY_ERROR


def test_incompatible_running_resume_blocks_before_mutating_interruption(
    tmp_path: Path,
) -> None:
    workspace, run_id, store = _complete(tmp_path)
    manifest_relative = f"runs/{run_id}/run.json"
    pipeline_relative = f"runs/{run_id}/pipeline.json"
    config_relative = f"runs/{run_id}/config/run_config.json"
    manifest = store.read_json_value(manifest_relative, max_bytes=1_000_000)
    manifest["status"] = "running"
    store.write_json(manifest_relative, manifest)
    pipeline = store.read_json_value(pipeline_relative, max_bytes=1_000_000)
    pipeline["ordered_stages"][0].update({"status": "running", "attempt_count": 1, "result": None})
    store.write_json(pipeline_relative, pipeline)
    config = store.read_json_value(config_relative, max_bytes=1_000_000)
    config["n"] = 5
    store.write_json(config_relative, config)
    before = (
        (tmp_path / "runs" / run_id / "run.json").read_bytes(),
        (tmp_path / "runs" / run_id / "pipeline.json").read_bytes(),
    )

    with pytest.raises(OperationalError) as failure:
        RunOperations(workspace).resume(run_id)
    assert failure.value.code == ErrorCode.INTEGRITY_ERROR
    after = (
        (tmp_path / "runs" / run_id / "run.json").read_bytes(),
        (tmp_path / "runs" / run_id / "pipeline.json").read_bytes(),
    )
    assert after == before


@pytest.mark.parametrize("field", ["instance_hash", "counting_convention", "provenance"])
def test_comparison_rejects_crossed_scientific_identity(tmp_path: Path, field: str) -> None:
    from tests.pipeline.test_pipeline import prepared_runner

    runner = prepared_runner(tmp_path)
    try:
        assert runner.handlers.exact() is None
        assert runner.handlers.reference() is None
        relative = runner.repository.layout.artifact("reference_result.json")
        payload = runner.store.read_json_value(relative, max_bytes=1_000_000)
        if field == "instance_hash":
            payload["instance_hash"] = "sha256:" + "0" * 64
        elif field == "counting_convention":
            payload["counting_convention"] = "incompatible-convention"
        else:
            payload["engine"] = {"id": "other", "version": "1"}
            payload["metrics"]["producer"] = payload["engine"]
        runner.store.write_json(relative, payload)

        failure = runner.handlers.comparison(None)
        assert failure == ErrorCode.INTEGRITY_ERROR
        runner.handlers.metrics()
        runner.handlers.report(RunStatus.FAILED)
        assert runner.results[StageId.COMPARE_RESULTS].status == "failed"
        assert runner.results[StageId.COLLECT_METRICS].status == "success"
        assert runner.results[StageId.EXPORT_REPORT].status == "success"
    finally:
        runner.close()
