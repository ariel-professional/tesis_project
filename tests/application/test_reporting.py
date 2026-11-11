from pathlib import Path

import pytest

from tesis_proyect.application.inspection import RunQueryService
from tesis_proyect.models.common import Diagnostic
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import ErrorCode, RunStatus, StageId
from tesis_proyect.models.reports import ReportMethods
from tesis_proyect.pipeline.orchestrator import PipelineCoordinator
from tesis_proyect.reporting.render import (
    render_run_inspection_human,
    render_stage_inspection_human,
)
from tests.contracts.test_foundation import valid_config
from tests.pipeline.test_pipeline import create_run

pytestmark = pytest.mark.integration


def test_human_run_inspection_explains_all_lifecycle_conclusions(tmp_path: Path) -> None:
    data = valid_config()
    data["source"] = {"kind": "inline", "edges": [[1, 2]]}
    workspace, run_id = create_run(tmp_path, ExperimentConfig.model_validate(data))
    service = RunQueryService(workspace)

    created_view = service.inspect_run(run_id)
    created_report = service.report_summary(run_id)
    created = render_run_inspection_human(created_view, created_report)
    assert "No canonical instance is available." in created
    assert "No structural analysis is available." in created
    assert "Exact: unavailable" in created
    assert "Comparison\n  Unavailable" in created
    assert "Commands: run, cancel, inspect" in created
    assert "No conclusive scientific result is available yet." in created

    PipelineCoordinator(workspace, run_id).run()
    completed_view = service.inspect_run(run_id)
    completed_report = service.report_summary(run_id)
    comparison = completed_report.comparison
    assert comparison is not None

    running_view = completed_view.model_copy(
        update={"run": completed_view.run.model_copy(update={"status": RunStatus.RUNNING})}
    )
    assert "previous runner no longer owns the lock" in render_run_inspection_human(
        running_view, completed_report
    )

    diagnostic = Diagnostic(
        code=ErrorCode.LOOP_EDGE,
        domain_error_code=2,
        message="Loop edge.",
        edge_index=0,
        edge=[1, 1],
    )
    failed_view = completed_view.model_copy(
        update={"run": completed_view.run.model_copy(update={"status": RunStatus.FAILED})}
    )
    failed_report = completed_report.model_copy(
        update={
            "run_status": RunStatus.FAILED,
            "diagnostics": [diagnostic],
            "methods": ReportMethods(exact=None, reference=None),
            "comparison": None,
        }
    )
    failed = render_run_inspection_human(failed_view, failed_report)
    assert "LOOP_EDGE: Loop edge." in failed
    assert "resume, inspect, export" in failed
    assert "1 domain diagnostic(s)" in failed

    cancelled_view = completed_view.model_copy(
        update={"run": completed_view.run.model_copy(update={"status": RunStatus.CANCELLED})}
    )
    cancelled_report = completed_report.model_copy(update={"run_status": RunStatus.CANCELLED})
    cancelled = render_run_inspection_human(cancelled_view, cancelled_report)
    assert "cancelled; available evidence may be incomplete" in cancelled
    assert "cancelled runs are terminal" in cancelled

    match = comparison.model_copy(
        update={
            "status": "match",
            "value_exact": 6,
            "value_reference": 6,
            "reason": None,
        }
    )
    match_report = completed_report.model_copy(update={"comparison": match})
    assert "Both methods agree on 6" in render_run_inspection_human(completed_view, match_report)

    mismatch = match.model_copy(update={"status": "mismatch", "value_exact": 5})
    mismatch_report = completed_report.model_copy(update={"comparison": mismatch})
    mismatch_text = render_run_inspection_human(completed_view, mismatch_report)
    assert "mismatch: exact=5, reference=6" in mismatch_text
    assert "methods disagree: exact=5, reference=6" in mismatch_text


def test_human_stage_inspection_explains_skip_and_missing_evidence(tmp_path: Path) -> None:
    data = valid_config()
    data["source"] = {"kind": "inline", "edges": []}
    data["integer_limits"]["reference_max_n"] = 1
    workspace, run_id = create_run(tmp_path, ExperimentConfig.model_validate(data))
    PipelineCoordinator(workspace, run_id).run()
    service = RunQueryService(workspace)
    reference = service.inspect_stage(run_id, StageId.RUN_REFERENCE_METHOD)
    rendered = render_stage_inspection_human(reference)
    assert "Skip: own/BRUTE_FORCE_LIMIT_EXCEEDED" in rendered
    assert "reference_result.json" in rendered

    without_evidence = reference.model_copy(
        update={"result": reference.result.model_copy(update={"outcome": None, "artifacts": []})}
    )
    rendered_missing = render_stage_inspection_human(without_evidence)
    assert "Outcome\n  Unavailable" in rendered_missing
    assert "Artifacts\n  None" in rendered_missing
