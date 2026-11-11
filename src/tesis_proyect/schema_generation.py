from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from tesis_proyect.models.common import StructuredError
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.execution import Instance, InstanceCandidate, PipelineState, RunManifest
from tesis_proyect.models.protocols import (
    ControlRequest,
    ControlResponse,
    EventEnvelope,
    RunInspection,
    StageInspection,
    WorkerRequest,
    WorkerResponse,
)
from tesis_proyect.models.reports import ReportSummary
from tesis_proyect.models.scientific import (
    ComparisonResult,
    CountingResult,
    LinearForestAnalysis,
    ValidationResult,
)
from tesis_proyect.models.stages import StageResult

SCHEMAS: dict[str, Any] = {
    "comparison-result": ComparisonResult,
    "control-request": ControlRequest,
    "control-response": ControlResponse,
    "counting-result": CountingResult,
    "event-envelope": EventEnvelope,
    "experiment-config": ExperimentConfig,
    "instance": Instance,
    "instance-candidate": InstanceCandidate,
    "linear-forest-analysis": LinearForestAnalysis,
    "pipeline-state": PipelineState,
    "report-summary": ReportSummary,
    "run-inspection": RunInspection,
    "run-manifest": RunManifest,
    "stage-inspection": StageInspection,
    "stage-result": StageResult,
    "structured-error": StructuredError,
    "validation-result": ValidationResult,
    "worker-request": WorkerRequest,
    "worker-response": WorkerResponse,
}


def generated() -> dict[str, str]:
    result: dict[str, str] = {}
    for name, model in sorted(SCHEMAS.items()):
        schema = TypeAdapter(model).json_schema(mode="serialization")
        result[f"{name}.schema.json"] = (
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    return result


def write_schemas(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    expected = generated()
    for path in root.glob("*.schema.json"):
        if path.name not in expected:
            path.unlink()
    for name, content in expected.items():
        (root / name).write_text(content, encoding="utf-8", newline="\n")
