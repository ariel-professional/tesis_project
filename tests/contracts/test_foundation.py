import ast
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from tesis_proyect.models.base import LargeNonNegativeInteger
from tesis_proyect.models.common import StructuredError
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import DOMAIN_ERROR_CODES, STAGE_ORDER, ErrorCode
from tesis_proyect.models.execution import PipelineState
from tesis_proyect.models.protocols import WorkerLimits
from tesis_proyect.schema_generation import generated


def valid_config() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "n": 4,
        "source": {"kind": "inline", "edges": [[1, 2, 3]]},
        "methods": {
            "exact": {"engine": "auto"},
            "reference": {"engine": "bruteforce_python_v1"},
        },
        "integer_limits": {
            "max_n": 12,
            "reference_max_n": 10,
            "exact_timeout_ms": 30000,
            "reference_timeout_ms": 30000,
            "cancellation_grace_ms": 1000,
            "control_connect_timeout_ms": 1000,
            "control_response_timeout_ms": 1000,
            "control_max_message_bytes": 16384,
            "input_max_bytes": 1048576,
            "event_max_payload_bytes": 65536,
            "worker_max_message_bytes": 65536,
            "runner_log_max_bytes": 5242880,
            "runner_log_backup_count": 3,
        },
        "persistence": {"policy": "normal"},
        "counting_convention": "undirected_paths_reverse_identified",
    }


def test_config_round_trip_and_only_default() -> None:
    model = ExperimentConfig.model_validate(valid_config())
    assert model.persistence.persist_events is False
    rebuilt = ExperimentConfig.model_validate_json(model.model_dump_json())
    assert rebuilt == model
    assert model.source.edges == [[1, 2, 3]]  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("n",), "4"),
        (("extra",), True),
        (("source", "edges"), [[1, 2.0]]),
        (("source", "unknown"), 1),
        (("schema_version",), "2.0.0"),
    ],
)
def test_config_rejects_coercion_extras_floats_and_version(
    path: tuple[str, ...], value: object
) -> None:
    data = valid_config()
    target = data
    for part in path[:-1]:
        target = target[part]  # type: ignore[index,assignment]
    target[path[-1]] = value  # type: ignore[index]
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(data)


def test_all_limits_and_methods_are_required() -> None:
    for key in list(valid_config()["integer_limits"]):  # type: ignore[arg-type]
        data = valid_config()
        del data["integer_limits"][key]  # type: ignore[index]
        with pytest.raises(ValidationError):
            ExperimentConfig.model_validate(data)
    for key in ("exact", "reference"):
        data = valid_config()
        del data["methods"][key]  # type: ignore[index]
        with pytest.raises(ValidationError):
            ExperimentConfig.model_validate(data)


def test_operational_limits_are_owned_by_the_experiment() -> None:
    data = valid_config()
    limits = data["integer_limits"]
    assert isinstance(limits, dict)
    for key in limits:
        limits[key] = 10**18
    data["n"] = 10**12
    model = ExperimentConfig.model_validate(data)
    assert model.n == 10**12
    assert model.integer_limits.reference_max_n == 10**18
    assert model.integer_limits.runner_log_backup_count == 10**18
    worker = WorkerLimits(
        timeout_ms=10**18,
        max_message_bytes=10**18,
        reference_max_n=10**18,
    )
    assert worker.reference_max_n == 10**18


@pytest.mark.parametrize(
    "key",
    [
        "max_n",
        "reference_max_n",
        "exact_timeout_ms",
        "reference_timeout_ms",
        "control_connect_timeout_ms",
        "control_response_timeout_ms",
        "control_max_message_bytes",
        "input_max_bytes",
        "event_max_payload_bytes",
        "worker_max_message_bytes",
        "runner_log_max_bytes",
    ],
)
def test_positive_operational_limits_reject_zero(key: str) -> None:
    data = valid_config()
    data["integer_limits"][key] = 0  # type: ignore[index]
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(data)


def test_zero_meaningful_operational_limits_remain_valid() -> None:
    data = valid_config()
    data["integer_limits"]["cancellation_grace_ms"] = 0  # type: ignore[index]
    data["integer_limits"]["runner_log_backup_count"] = 0  # type: ignore[index]
    ExperimentConfig.model_validate(data)


def test_large_integer_wire_boundary() -> None:
    adapter = TypeAdapter(LargeNonNegativeInteger)
    assert adapter.validate_python(9_007_199_254_740_991) == 9_007_199_254_740_991
    assert adapter.validate_python("9007199254740992") == "9007199254740992"
    for invalid in (-1, 9_007_199_254_740_992, "01", "42", 1.0, True):
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid)


def test_error_integer_map_is_exact_and_enforced() -> None:
    assert list(DOMAIN_ERROR_CODES.values()) == list(range(1, 15))
    error = StructuredError(
        schema_version="1.0.0",
        code=ErrorCode.MALFORMED_EDGE,
        domain_error_code=1,
        message="Malformed edge.",
        recoverable=False,
        details={},
        stage="validate_instance_edges",
    )
    assert error.domain_error_code == 1
    with pytest.raises(ValidationError):
        StructuredError.model_validate({**error.model_dump(), "domain_error_code": 2})


def test_pipeline_requires_exact_stage_order() -> None:
    stages = [
        {
            "ordinal": ordinal,
            "stage": stage,
            "status": "pending",
            "attempt_count": 0,
            "result": None,
        }
        for ordinal, stage in enumerate(STAGE_ORDER, start=1)
    ]
    model = PipelineState(schema_version="1.0.0", pipeline_version="1.0.0", ordered_stages=stages)
    assert len(model.ordered_stages) == 10
    with pytest.raises(ValidationError):
        PipelineState(schema_version="1.0.0", pipeline_version="1.0.0", ordered_stages=stages[:-1])


def test_generated_comparison_schema_describes_public_fields() -> None:
    schema = json.loads(generated()["comparison-result.schema.json"])
    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    assert schema["$defs"]["ComparisonStatus"]["enum"] == ["match", "mismatch", "not_applicable"]
    assert {"status", "value_exact", "value_reference", "instance_hash"} <= set(schema["required"])


def test_traceability_has_exactly_42_unique_requirements() -> None:
    payload = json.loads(Path("traceability/requirements.json").read_text(encoding="utf-8"))
    ids = [item["id"] for item in payload["requirements"]]
    assert len(ids) == len(set(ids)) == 42
    assert {item for row in payload["requirements"] for item in row["tests"]} == {
        "BASE22",
        "STATE",
        "FAILURE",
        "CANCEL",
        "RESUME",
        "HASH",
        "CLI-CONTRACT",
        "SECURITY",
    }


def test_traceability_groups_resolve_to_existing_test_files() -> None:
    root = Path(__file__).parents[2]
    requirements = json.loads((root / "traceability" / "requirements.json").read_text())
    suites = requirements["suites"]
    referenced = {group for item in requirements["requirements"] for group in item["tests"]}
    assert referenced == set(suites)
    assert all(paths for paths in suites.values())
    assert all((root / path).is_file() for paths in suites.values() for path in paths)


def test_every_requirement_names_existing_test_functions() -> None:
    root = Path(__file__).parents[2]
    requirements = json.loads((root / "traceability" / "requirements.json").read_text())
    cache: dict[Path, set[str]] = {}
    for requirement in requirements["requirements"]:
        assert requirement["evidence"], requirement["id"]
        for reference in requirement["evidence"]:
            path_text, separator, function = reference.partition("::")
            assert separator and function.startswith("test_"), reference
            path = root / path_text
            assert path.is_file(), reference
            if path not in cache:
                tree = ast.parse(path.read_text(encoding="utf-8"))
                cache[path] = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
            assert function in cache[path], reference
