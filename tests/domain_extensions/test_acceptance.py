from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tesis_domain_extensions.domains.inspection_route.contracts import InspectionRouteResult

pytestmark = [pytest.mark.acceptance, pytest.mark.integration]


def test_inspection_route_comparative_study_end_to_end(
    tmp_path: Path,
    example_root: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    base = [sys.executable, "-m", "tesis_domain_extensions"]
    prepared = subprocess.run(
        [
            *base,
            "prepare",
            "--config",
            str(example_root / "comparison.json"),
            "--workspace",
            str(workspace),
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert prepared.returncode == 0, prepared.stderr
    experiment = json.loads(prepared.stdout)
    experiment_id = experiment["domain_experiment_id"]
    assert not (workspace / "experiments" / f"{experiment_id}.json").exists()

    process = subprocess.run(
        [
            *base,
            "run",
            experiment["reference"],
            "--workspace",
            str(workspace),
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert process.returncode == 0, process.stderr
    result = InspectionRouteResult.model_validate_json(process.stdout)
    assert result.comparison_status == "conclusive"
    assert result.most_flexible_scenario_ids == ["recorrido-libre"]
    assert [item.route_count.value if item.route_count else None for item in result.scenarios] == [
        1440,
        20160,
        1,
        None,
    ]
    assert result.generation.declared_scenarios == 4
    assert result.generation.valid_scenarios == 3
    assert result.generation.invalid_scenarios == 1
    assert result.generation.core_cases == 3
    invalid = result.scenarios[-1]
    assert invalid.validation_issue is not None
    assert invalid.validation_issue.reason == "degree_exceeded"
    assert invalid.core_run_id is None
    root = workspace / "domain_runs" / result.execution.domain_run_id
    assert (root / "domain_run.json").is_file()
    assert (root / "result.json").is_file()
    assert (root / "report.md").is_file()
