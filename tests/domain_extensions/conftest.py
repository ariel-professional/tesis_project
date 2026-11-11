from __future__ import annotations

import json
from pathlib import Path

import pytest

from tesis_domain_extensions.adapters import ProjectedCase
from tesis_domain_extensions.domains.inspection_route.adapter import InspectionRouteAdapter
from tesis_domain_extensions.domains.inspection_route.contracts import (
    InspectionRouteConfig,
    InspectionRouteProjectionContext,
)

RUN_ID = "12345678-1234-4234-8234-123456789abc"


@pytest.fixture
def example_root() -> Path:
    return Path("examples/domains/inspection-route")


@pytest.fixture
def partial_config(example_root: Path) -> InspectionRouteConfig:
    return InspectionRouteAdapter().parse_config((example_root / "comparison.json").read_bytes())


@pytest.fixture
def projection_context(
    partial_config: InspectionRouteConfig,
) -> InspectionRouteProjectionContext:
    return InspectionRouteAdapter().project(partial_config).context


@pytest.fixture
def projected_case(
    partial_config: InspectionRouteConfig,
    projection_context: InspectionRouteProjectionContext,
) -> ProjectedCase:
    return next(InspectionRouteAdapter().iter_cases(partial_config, projection_context))


@pytest.fixture
def success_report(projected_case: ProjectedCase) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "run_id": RUN_ID,
        "experiment_id": projected_case.core_experiment_id,
        "run_status": "completed",
        "instance": {
            "n": 8,
            "edges": [[2, 3], [6, 7]],
        },
        "structure": {
            "case_type": "matching",
            "components": [{"vertices": [2, 3]}, {"vertices": [6, 7]}],
            "free_vertices": [1, 4, 5, 8],
            "blocks": 6,
        },
        "methods": {
            "exact": {
                "status": "skipped",
                "skip": {
                    "code": "EXACT_ENGINE_NOT_AVAILABLE",
                    "message": "The exact engine is not available.",
                },
            },
            "reference": {
                "status": "success",
                "value": 1440,
                "engine": {"id": "bruteforce-python", "version": "1"},
                "counting_convention": "undirected_paths_reverse_identified",
                "metrics": {"duration_ms": 4, "candidates_examined": 20160},
            },
        },
        "comparison": {"status": "not_applicable"},
        "diagnostics": [],
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
