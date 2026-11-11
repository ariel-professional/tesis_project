from __future__ import annotations

import unicodedata
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from tesis_proyect.models.common import (
    ArtifactRef,
    Cancellation,
    Diagnostic,
    ExperimentId,
    GeneratorMetadata,
    ProducerRef,
    RunId,
    StructuredError,
    Timestamp,
)
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import STAGE_ORDER, ErrorCode
from tesis_proyect.models.execution import Instance, PipelineState, StageAttempt, Versions
from tesis_proyect.models.protocols import (
    ControlResponse,
    EventEnvelope,
    RunCreatedPayload,
    StageStartedPayload,
    WorkerResponse,
)
from tesis_proyect.models.scientific import (
    ComparisonResult,
    CountingResult,
    LinearForestAnalysis,
    ValidationResult,
)
from tesis_proyect.models.stages import MetricsOutcome, StageResult
from tesis_proyect.persistence.json_store import JsonStore
from tesis_proyect.pipeline.orchestrator import PipelineCoordinator
from tests.contracts.test_foundation import valid_config
from tests.pipeline.test_pipeline import create_run

NOW = "2026-08-05T15:30:00.000Z"
RUN_ID = "12345678-1234-4234-8234-123456789abc"


@pytest.mark.parametrize(
    ("n", "family", "parameters"),
    [
        (2, "matching", {"edge_count": 2}),
        (2, "single_path", {"edge_count": 2}),
        (3, "multiple_paths", {"component_edge_lengths": [1, 1]}),
        (3, "invalid_cycle", {"cycle_length": 4}),
        (1, "invalid_duplicate", {}),
        (3, "invalid_degree3", {}),
        (4, "empty", {"edge_count": 0}),
    ],
)
def test_generator_cross_field_boundaries(
    n: int, family: str, parameters: dict[str, object]
) -> None:
    data = valid_config()
    data["n"] = n
    data["source"] = {
        "kind": "generator",
        "family": family,
        "generator_version": "builtin-v1",
        "seed": 0,
        "parameters": parameters,
    }
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(data)


def test_config_rejects_n_above_maximum() -> None:
    data = valid_config()
    data["n"] = 13
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(data)


def test_inline_float_is_rejected_inside_nested_object() -> None:
    data = valid_config()
    data["source"] = {"kind": "inline", "edges": [{"nested": [1, {"float": 1.5}]}]}
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(data)


def test_identifier_and_error_bounds_are_enforced() -> None:
    base = {
        "schema_version": "1.0.0",
        "code": "INTERNAL_ERROR",
        "domain_error_code": None,
        "message": "Failure.",
        "recoverable": False,
        "details": {},
        "stage": None,
    }
    StructuredError.model_validate(base)
    for mutation in (
        {"domain_error_code": 1},
        {"details": {str(index): index for index in range(33)}},
        {"details": {"a": {"b": {"c": {"d": {"e": 1}}}}}},
    ):
        with pytest.raises(ValidationError):
            StructuredError.model_validate({**base, **mutation})
    with pytest.raises(ValidationError):
        Diagnostic.model_validate(
            {
                "code": "LOOP_EDGE",
                "domain_error_code": 1,
                "message": "Loop.",
                "edge_index": 0,
                "edge": [1, 1],
            }
        )
    for model, payload in (
        (ArtifactRef, {"path": "a", "sha256": "bad", "size_bytes": 0}),
        (ProducerRef, {"id": "bad token!", "version": "1"}),
    ):
        with pytest.raises(ValidationError):
            model.model_validate(payload)
    for alias, value in (
        (ExperimentId, "Bad ID"),
        (RunId, "12345678-1234-1234-8234-123456789abc"),
        (RunId, "12345678-1234-4234-8234-123456789abC"),
        (Timestamp, "2026-08-05"),
    ):
        with pytest.raises(ValidationError):
            TypeAdapter(alias).validate_python(value)


def test_semantic_strings_are_nfc_but_candidate_values_remain_opaque() -> None:
    composed = "cancelación"
    decomposed = unicodedata.normalize("NFD", composed)
    cancellation = Cancellation(requested_at=NOW, origin="cli", reason=decomposed)
    assert cancellation.reason == composed
    data = valid_config()
    data["source"] = {"kind": "file", "path": f"datos/{decomposed}.json"}
    config = ExperimentConfig.model_validate(data)
    assert config.source.path == f"datos/{composed}.json"  # type: ignore[union-attr]
    data["source"] = {"kind": "inline", "edges": [[1, {decomposed: decomposed}]]}
    opaque = ExperimentConfig.model_validate(data)
    assert opaque.source.edges == [[1, {decomposed: decomposed}]]  # type: ignore[union-attr]


def test_persisted_model_invariants_use_real_pipeline_evidence(tmp_path: Path) -> None:
    data = valid_config()
    data["source"] = {"kind": "inline", "edges": [[1, 2]]}
    workspace, run_id = create_run(tmp_path, ExperimentConfig.model_validate(data))
    PipelineCoordinator(workspace, run_id, clock=lambda: NOW).run()
    store = JsonStore(workspace)

    instance = store.read_json_value(f"runs/{run_id}/artifacts/instance.json", max_bytes=1_000_000)
    for edges in ([[2, 1]], [[1, 3], [1, 2]], [[1, 2], [1, 2]]):
        invalid = {**instance, "edges": edges}
        with pytest.raises(ValidationError):
            Instance.model_validate(invalid)

    pipeline = store.read_json_value(f"runs/{run_id}/pipeline.json", max_bytes=1_000_000)
    pending_with_result = deepcopy(pipeline)
    pending_with_result["ordered_stages"][0]["status"] = "pending"
    with pytest.raises(ValidationError):
        PipelineState.model_validate(pending_with_result)
    two_running = deepcopy(pipeline)
    for index in (0, 1):
        two_running["ordered_stages"][index]["status"] = "running"
        two_running["ordered_stages"][index]["result"] = None
    with pytest.raises(ValidationError):
        PipelineState.model_validate(two_running)

    result = store.read_json_value(
        f"runs/{run_id}/stages/01_define_experiment.json", max_bytes=1_000_000
    )
    mutations = []
    no_attempts = deepcopy(result)
    no_attempts["attempts"] = []
    mutations.append(no_attempts)
    wrong_number = deepcopy(result)
    wrong_number["attempts"][0]["number"] = 2
    mutations.append(wrong_number)
    wrong_duration = deepcopy(result)
    wrong_duration["duration_ms"] += 1
    mutations.append(wrong_duration)
    wrong_error = deepcopy(result)
    wrong_error["error"] = {
        "schema_version": "1.0.0",
        "code": "INTERNAL_ERROR",
        "domain_error_code": None,
        "message": "Failure.",
        "recoverable": False,
        "details": {},
        "stage": None,
    }
    mutations.append(wrong_error)
    wrong_outcome = deepcopy(result)
    wrong_outcome["stage"] = "load_or_generate_instance"
    mutations.append(wrong_outcome)
    for invalid in mutations:
        with pytest.raises(ValidationError):
            StageResult.model_validate(invalid)


def test_summary_and_validation_consistency() -> None:
    diagnostic = {
        "code": "LOOP_EDGE",
        "domain_error_code": 2,
        "message": "Loop.",
        "edge_index": 0,
        "edge": [1, 1],
    }
    for value in (
        {"schema_version": "1.0.0", "valid": True, "errors": [diagnostic], "warnings": []},
        {"schema_version": "1.0.0", "valid": False, "errors": [], "warnings": []},
    ):
        with pytest.raises(ValidationError):
            ValidationResult.model_validate(value)
    base = {
        "schema_version": "1.0.0",
        "components": [{"vertices": [1, 2], "edges": [[1, 2]], "edge_length": 1}],
        "component_lengths": [1],
        "free_vertices": [3],
        "free_vertex_count": 1,
        "blocks": 2,
        "case_type": "single_path",
    }
    for mutation in (
        {"component_lengths": [2]},
        {"free_vertex_count": 0},
        {"blocks": 1},
    ):
        with pytest.raises(ValidationError):
            LinearForestAnalysis.model_validate({**base, **mutation})


def test_stage_attempt_and_comparison_variants_reject_contradictions() -> None:
    metrics = {
        "duration_ms": 0,
        "worker_duration_ms": None,
        "candidates_examined": None,
        "peak_memory_bytes": None,
        "producer": None,
    }
    attempt = {
        "number": 1,
        "started_at": NOW,
        "finished_at": NOW,
        "duration_ms": 0,
        "status": "success",
        "error": None,
        "skip": None,
        "metrics": metrics,
        "termination": "not_applicable",
    }
    error = {
        "schema_version": "1.0.0",
        "code": "RUN_CANCELLED",
        "domain_error_code": 10,
        "message": "Cancelled.",
        "recoverable": False,
        "details": {},
        "stage": "run_exact_method",
    }
    skip = {"kind": "own", "code": "EXACT_ENGINE_NOT_AVAILABLE", "message": "Skipped."}
    for mutation in (
        {"error": error},
        {"status": "failed"},
        {"status": "skipped"},
        {"status": "cancelled", "error": None},
        {
            "status": "cancelled",
            "error": {**error, "code": "STAGE_TIMEOUT", "domain_error_code": 9},
        },
        {"status": "success", "skip": skip},
        {
            "status": "skipped",
            "skip": {
                "kind": "dependency",
                "code": "EXACT_ENGINE_NOT_AVAILABLE",
                "message": "Not a dependency.",
            },
        },
    ):
        with pytest.raises(ValidationError):
            StageAttempt.model_validate({**attempt, **mutation})

    producer = {"id": "engine", "version": "1"}
    comparison = {
        "schema_version": "1.0.0",
        "status": "match",
        "value_exact": 1,
        "value_reference": 1,
        "exact": producer,
        "reference": producer,
        "counting_convention": "undirected_paths_reverse_identified",
        "reason": None,
        "instance_hash": "sha256:" + "0" * 64,
    }
    for mutation in (
        {"value_exact": None},
        {"status": "not_applicable"},
        {"value_exact": 2},
        {"status": "mismatch"},
    ):
        with pytest.raises(ValidationError):
            ComparisonResult.model_validate({**comparison, **mutation})


def test_versions_generator_counting_and_metrics_invariants(tmp_path: Path) -> None:
    data = valid_config()
    data["source"] = {"kind": "inline", "edges": [[1, 2]]}
    workspace, run_id = create_run(tmp_path, ExperimentConfig.model_validate(data))
    PipelineCoordinator(workspace, run_id, clock=lambda: NOW).run()
    store = JsonStore(workspace)
    manifest = store.read_json_value(f"runs/{run_id}/run.json", max_bytes=1_000_000)
    for field, value in (
        ("app", {"id": "tesis-proyect", "version": "9"}),
        ("pipeline", {"id": "increment-1", "version": "9"}),
        ("exact", {"id": "unexpected", "version": "1"}),
        ("reference", {"id": "bruteforce-python", "version": "9"}),
    ):
        invalid = deepcopy(manifest["versions"])
        invalid[field] = value
        with pytest.raises(ValidationError):
            Versions.model_validate(invalid)

    with pytest.raises(ValidationError):
        GeneratorMetadata.model_validate(
            {
                "kind": "generator",
                "family": "matching",
                "generator_version": "builtin-v1",
                "seed": 0,
                "parameters": {},
            }
        )

    exact = store.read_json_value(f"runs/{run_id}/artifacts/exact_result.json", max_bytes=1_000_000)
    exact["metrics"]["producer"] = {"id": "other", "version": "1"}
    with pytest.raises(ValidationError):
        TypeAdapter(CountingResult).validate_python(exact)

    metrics_stage = store.read_model(
        f"runs/{run_id}/stages/09_collect_metrics.json",
        StageResult,
        max_bytes=1_000_000,
    )
    assert isinstance(metrics_stage.outcome, MetricsOutcome)
    stages = [item.model_dump(mode="json") for item in metrics_stage.outcome.stages]
    with pytest.raises(ValidationError):
        MetricsOutcome(kind="metrics_collection", stages=stages[:-1])
    stages[0], stages[1] = stages[1], stages[0]
    with pytest.raises(ValidationError):
        MetricsOutcome(kind="metrics_collection", stages=stages)


def test_event_and_control_discriminants_are_cross_validated() -> None:
    created = RunCreatedPayload(status="created")
    with pytest.raises(ValidationError):
        EventEnvelope(
            schema_version="1.0.0",
            event="stage_started",
            run_id=RUN_ID,
            timestamp=NOW,
            stage="validate_experiment_definition",
            payload=created,
        )
    with pytest.raises(ValidationError):
        EventEnvelope(
            schema_version="1.0.0",
            event="run_created",
            run_id=None,
            timestamp=NOW,
            stage=None,
            payload=created,
        )
    with pytest.raises(ValidationError):
        EventEnvelope(
            schema_version="1.0.0",
            event="run_created",
            run_id=RUN_ID,
            timestamp=NOW,
            stage="validate_experiment_definition",
            payload=created,
        )
    StageStartedPayload(status="running", attempt=1)
    base = {
        "schema_version": "1.0.0",
        "request_id": RUN_ID,
        "run_id": RUN_ID,
        "status": "terminal",
        "cancellation": None,
        "error": None,
    }
    for mutation in (
        {"status": "accepted"},
        {"status": "rejected"},
        {
            "error": {
                "schema_version": "1.0.0",
                "code": "INTERNAL_ERROR",
                "domain_error_code": None,
                "message": "Failure.",
                "recoverable": False,
                "details": {},
                "stage": None,
            }
        },
    ):
        with pytest.raises(ValidationError):
            ControlResponse.model_validate({**base, **mutation})

    worker = {
        "schema_version": "1.0.0",
        "request_id": RUN_ID,
        "run_id": RUN_ID,
        "stage": "run_exact_method",
        "status": "failed",
        "result": None,
        "error": None,
        "metrics": {
            "duration_ms": 0,
            "worker_duration_ms": 0,
            "candidates_examined": None,
            "peak_memory_bytes": None,
            "producer": {"id": "worker", "version": "1"},
        },
    }
    for mutation in ({}, {"status": "success"}):
        with pytest.raises(ValidationError):
            WorkerResponse.model_validate({**worker, **mutation})


def test_stage_order_constant_remains_ten_entries() -> None:
    assert len(STAGE_ORDER) == 10
    assert STAGE_ORDER[0] == "define_experiment"
    assert ErrorCode.RUNNER_INTERRUPTED.value == "RUNNER_INTERRUPTED"
