from __future__ import annotations

import json
from itertools import permutations
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import STAGE_ORDER, ErrorCode, RunStatus
from tesis_proyect.models.execution import PipelineState
from tesis_proyect.models.reports import ReportSummary
from tesis_proyect.models.scientific import ComparisonResult, CountingResult, LinearForestAnalysis
from tesis_proyect.models.stages import StageResult
from tesis_proyect.persistence.json_store import JsonStore
from tesis_proyect.pipeline.orchestrator import PipelineCoordinator
from tests.contracts.test_foundation import valid_config
from tests.pipeline.test_pipeline import create_run

pytestmark = pytest.mark.acceptance

CATALOG = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "base22.json").read_text(encoding="utf-8")
)
CASES = CATALOG["cases"]
ALL_OUTPUTS = {
    "artifacts/instance_candidate.json",
    "artifacts/instance.json",
    "artifacts/structure_summary.json",
    "artifacts/exact_result.json",
    "artifacts/reference_result.json",
    "artifacts/comparison_result.json",
    "reports/result.json",
    "reports/report.md",
}


def _independent_oracle(n: int, raw_edges: list[list[int]]) -> int:
    required = {tuple(sorted(edge)) for edge in raw_edges}
    count = 0
    for candidate in permutations(range(1, n + 1)):
        if candidate > candidate[::-1]:
            continue
        edges = {tuple(sorted((candidate[index], candidate[index + 1]))) for index in range(n - 1)}
        count += required <= edges
    return count


def _existing_outputs(root: Path) -> set[str]:
    return {relative for relative in ALL_OUTPUTS if (root / Path(*relative.split("/"))).is_file()}


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_base22_complete_acceptance_profile(tmp_path: Path, case: dict[str, Any]) -> None:
    profile = CATALOG["profiles"][case["profile"]]
    data = valid_config()
    data["n"] = case["n"]
    data["source"] = {"kind": "inline", "edges": case["edges"]}
    workspace, run_id = create_run(tmp_path, ExperimentConfig.model_validate(data))
    manifest = PipelineCoordinator(workspace, run_id).run()
    store = JsonStore(workspace)
    root = tmp_path / "runs" / run_id

    assert manifest.status == RunStatus(profile["run_status"])
    pipeline = store.read_model(f"runs/{run_id}/pipeline.json", PipelineState, max_bytes=1_000_000)
    assert [state.stage for state in pipeline.ordered_stages] == list(STAGE_ORDER)
    assert [state.status.value for state in pipeline.ordered_stages] == profile["stage_statuses"]
    assert all(state.result is not None for state in pipeline.ordered_stages)
    assert _existing_outputs(root) == set(profile["artifacts"])
    assert len(list((root / "stages").glob("*.json"))) == 10

    report = store.read_model(
        f"runs/{run_id}/reports/result.json", ReportSummary, max_bytes=1_000_000
    )
    assert report.run_status == manifest.status
    assert report.metrics is not None and len(report.metrics) == 8
    assert [metric.stage for metric in report.metrics] == list(STAGE_ORDER[:8])

    if case["analysis"] is not None:
        analysis = store.read_model(
            f"runs/{run_id}/artifacts/structure_summary.json",
            LinearForestAnalysis,
            max_bytes=1_000_000,
        )
        expected = case["analysis"]
        assert analysis.case_type == expected["case_type"]
        assert analysis.component_lengths == expected["component_lengths"]
        assert analysis.free_vertices == expected["free_vertices"]
        assert analysis.blocks == expected["blocks"]

        exact = TypeAdapter(CountingResult).validate_python(
            store.read_json_value(f"runs/{run_id}/artifacts/exact_result.json", max_bytes=1_000_000)
        )
        reference = TypeAdapter(CountingResult).validate_python(
            store.read_json_value(
                f"runs/{run_id}/artifacts/reference_result.json", max_bytes=1_000_000
            )
        )
        comparison = store.read_model(
            f"runs/{run_id}/artifacts/comparison_result.json",
            ComparisonResult,
            max_bytes=1_000_000,
        )
        assert exact.status == "success"
        assert reference.status == case["reference"]["status"]
        if reference.status == "success":
            assert reference.value == case["reference"]["value"]
            assert reference.value == _independent_oracle(case["n"], case["edges"])
        else:
            assert reference.skip.code.value == case["reference"]["code"]
        if reference.status == "success":
            assert exact.value == reference.value
            assert exact.value == _independent_oracle(case["n"], case["edges"])
            assert comparison.status == "match"
            assert comparison.reason is None
        else:
            assert comparison.status == "not_applicable"
            assert comparison.reason is not None
            assert comparison.reason.code == ErrorCode.BRUTE_FORCE_LIMIT_EXCEEDED
        assert report.diagnostics == []
    else:
        failed_ordinal = 3 if case["profile"] == "invalid_edge" else 4
        failed_stage = STAGE_ORDER[failed_ordinal - 1]
        result = store.read_model(
            f"runs/{run_id}/stages/{failed_ordinal:02d}_{failed_stage.value}.json",
            StageResult,
            max_bytes=1_000_000,
        )
        assert result.error is not None
        assert result.error.code.value == case["diagnostic"]
        assert {diagnostic.code.value for diagnostic in report.diagnostics} >= {case["diagnostic"]}


def test_base22_catalog_is_independent_complete_and_profiled() -> None:
    assert CATALOG["schema_version"] == "1.0.0"
    assert set(CATALOG["profiles"]) == {
        "valid",
        "reference_skip",
        "invalid_edge",
        "invalid_forest",
    }
    identifiers = [case["id"] for case in CASES]
    assert len(identifiers) == len(set(identifiers)) == 22
    assert all(case["profile"] in CATALOG["profiles"] for case in CASES)
