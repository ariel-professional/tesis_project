from pathlib import Path
from uuid import UUID

import pytest

from tesis_proyect.application.experiments import ExperimentService
from tesis_proyect.application.inspection import RunQueryService, normalize_run_prefix
from tesis_proyect.domain.validation import validate_edges, validate_linear_forest
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import ErrorCode
from tesis_proyect.persistence.json_store import JsonStore
from tesis_proyect.persistence.workspace import Workspace
from tesis_proyect.pipeline.sources import (
    BUILTIN_V1_COUNTER_ASCII,
    generate_edges,
    materialize_candidate,
)
from tests.contracts.test_foundation import valid_config

pytestmark = pytest.mark.integration

RUN_ID = UUID("12345678-1234-4234-8234-123456789abc")


def service(tmp_path: Path) -> ExperimentService:
    return ExperimentService(
        Workspace.open(tmp_path),
        uuid_factory=lambda: RUN_ID,
        clock=lambda: "2026-08-05T15:30:00.000Z",
    )


def generator_config(
    n: int, family: str, parameters: dict[str, object], seed: int = 7
) -> ExperimentConfig:
    data = valid_config()
    data["n"] = n
    data["source"] = {
        "kind": "generator",
        "family": family,
        "generator_version": "builtin-v1",
        "seed": seed,
        "parameters": parameters,
    }
    return ExperimentConfig.model_validate(data)


def test_save_and_create_immutable_run(tmp_path: Path) -> None:
    app = service(tmp_path)
    config = ExperimentConfig.model_validate(valid_config())
    app.save_experiment("baseline", config)
    with pytest.raises(OperationalError) as collision:
        app.save_experiment("baseline", config)
    assert collision.value.code == ErrorCode.ID_COLLISION
    run = app.create_run("baseline")
    assert run.run_id == str(RUN_ID)
    assert run.status == "created"
    run_root = tmp_path / "runs" / str(RUN_ID)
    assert (run_root / "run.json").is_file()
    assert (run_root / "pipeline.json").is_file()
    assert (run_root / "config" / "run_config.json").is_file()
    assert (run_root / "execution.lock").is_file()
    assert not list((run_root / "stages").iterdir())
    assert not list((run_root / "artifacts").iterdir())


def test_create_run_regenerates_colliding_generated_id(tmp_path: Path) -> None:
    second = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    ids = iter((RUN_ID, RUN_ID, second))
    app = ExperimentService(
        Workspace.open(tmp_path),
        uuid_factory=lambda: next(ids),
        clock=lambda: "2026-08-05T15:30:00.000Z",
    )
    config = ExperimentConfig.model_validate(valid_config())
    app.save_experiment("baseline", config)
    assert app.create_run("baseline").run_id == str(RUN_ID)
    assert app.create_run("baseline").run_id == str(second)


def test_create_run_failure_leaves_no_partial_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = service(tmp_path)
    app.save_experiment("atomic-run", ExperimentConfig.model_validate(valid_config()))
    original = app.store.write_json
    writes = 0

    def fail_second_write(*args: object, **kwargs: object) -> object:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OperationalError(ErrorCode.IO_ERROR, "Injected run creation failure.")
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(app.store, "write_json", fail_second_write)
    with pytest.raises(OperationalError, match="Injected run creation failure"):
        app.create_run("atomic-run")
    assert list((app.workspace.root / "runs").iterdir()) == []


def test_run_listing_filters_orders_warns_and_builds_unique_references(tmp_path: Path) -> None:
    workspace = Workspace.open(tmp_path)
    config = ExperimentConfig.model_validate(valid_config())
    ids_and_times = (
        (UUID("435b552c-231f-48ab-9223-4579538b1f55"), "2026-08-11T04:15:00.000Z"),
        (UUID("4f82a10d-b741-4bc0-8737-e4a7d7ea535e"), "2026-08-11T04:15:00.000Z"),
        (UUID("8a61c092-77ed-4b47-8f20-c7a51e430710"), "2026-08-10T23:50:12.000Z"),
    )
    ExperimentService(workspace).save_experiment("d1", config)
    ExperimentService(workspace).save_experiment("a3", config)
    for index, (run_id, timestamp) in enumerate(ids_and_times):
        ExperimentService(
            workspace,
            uuid_factory=lambda run_id=run_id: run_id,
            clock=lambda timestamp=timestamp: timestamp,
        ).create_run("d1" if index != 1 else "a3")
    corrupt = tmp_path / "runs" / "4aaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    corrupt.mkdir()
    invalid_name = tmp_path / "runs" / "4-not-a-run"
    invalid_name.mkdir()
    mismatched_id = "4bbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    (tmp_path / "runs" / mismatched_id).mkdir()
    JsonStore(workspace).write_json(
        f"runs/{mismatched_id}/run.json",
        RunQueryService(workspace).inspect_run(str(ids_and_times[0][0])).run,
    )
    unrelated = tmp_path / "runs" / "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    unrelated.mkdir()

    service = RunQueryService(workspace)
    listing = service.list_runs(prefix="4")
    assert [item.manifest.run_id for item in listing.runs] == [
        str(ids_and_times[0][0]),
        str(ids_and_times[1][0]),
    ]
    assert [item.reference for item in listing.runs] == ["435b552c", "4f82a10d"]
    assert listing.warnings == (
        "Warning: skipped runs/4-not-a-run: directory name is not a canonical run ID.",
        "Warning: skipped runs/4aaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa: "
        "run.json is missing or invalid.",
        "Warning: skipped runs/4bbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb: manifest run ID "
        "does not match its directory.",
    )
    assert [item.manifest.run_id for item in service.list_runs(experiment_id="d1").runs] == [
        str(ids_and_times[0][0]),
        str(ids_and_times[2][0]),
    ]
    assert [item.manifest.run_id for item in service.list_runs(prefix="435B552C-231F").runs] == [
        str(ids_and_times[0][0])
    ]
    assert service.list_runs(prefix="ffff").runs == ()


def test_run_reference_normalization_resolution_and_ambiguity(tmp_path: Path) -> None:
    assert normalize_run_prefix("4", minimum_length=1) == "4"
    assert normalize_run_prefix("435B552C-231F", minimum_length=1) == "435b552c231f"
    for invalid in ("", "xyz", "435b-552c", "435b552c--231f", "0" * 33):
        with pytest.raises(ValueError):
            normalize_run_prefix(invalid, minimum_length=1)

    workspace = Workspace.open(tmp_path)
    first = "12345678-1234-4234-8234-123456789abc"
    second = "12345678-2234-4234-8234-123456789abc"
    for run_id in (first, second):
        (tmp_path / "runs" / run_id).mkdir(parents=True)
    queries = RunQueryService(workspace)
    assert queries.resolve_run_reference(first) == first
    assert queries.resolve_run_reference("123456781") == first
    assert queries.short_reference(first) == "123456781"
    with pytest.raises(OperationalError) as ambiguous:
        queries.resolve_run_reference("12345678")
    assert ambiguous.value.code == ErrorCode.ID_COLLISION
    with pytest.raises(OperationalError) as missing:
        queries.resolve_run_reference("ffffffff")
    assert missing.value.code == ErrorCode.NOT_FOUND


def test_inline_candidate_preserves_malformed_edges(tmp_path: Path) -> None:
    config = ExperimentConfig.model_validate(valid_config())
    candidate = materialize_candidate(config, JsonStore(Workspace.open(tmp_path)))
    assert candidate.edge_data == [[1, 2, 3]]
    assert (
        validate_edges(candidate.n, candidate.edge_data).result.errors[0].code
        == ErrorCode.MALFORMED_EDGE
    )


def test_file_source_is_direct_array_and_preserves_float_for_stage_three(tmp_path: Path) -> None:
    (tmp_path / "input.json").write_text("[[1, 2.5]]\n", encoding="utf-8")
    data = valid_config()
    data["source"] = {"kind": "file", "path": "input.json"}
    config = ExperimentConfig.model_validate(data)
    store = JsonStore(Workspace.open(tmp_path))
    candidate = materialize_candidate(config, store)
    assert candidate.edge_data == [[1, 2.5]]
    assert validate_edges(4, candidate.edge_data).result.errors[0].code == ErrorCode.MALFORMED_EDGE
    (tmp_path / "object.json").write_text('{"edges": []}', encoding="utf-8")
    data["source"] = {"kind": "file", "path": "object.json"}
    with pytest.raises(OperationalError) as failure:
        materialize_candidate(ExperimentConfig.model_validate(data), store)
    assert failure.value.code == ErrorCode.SCHEMA_INVALID


@pytest.mark.parametrize(
    ("n", "family", "parameters", "stage", "code"),
    [
        (4, "invalid_loop", {}, 3, ErrorCode.LOOP_EDGE),
        (4, "invalid_duplicate", {}, 3, ErrorCode.DUPLICATE_EDGE),
        (
            4,
            "invalid_vertex_out_of_range",
            {"direction": "above"},
            3,
            ErrorCode.VERTEX_OUT_OF_RANGE,
        ),
        (4, "invalid_cycle", {"cycle_length": 3}, 4, ErrorCode.CYCLE_DETECTED),
        (5, "invalid_degree3", {}, 4, ErrorCode.MAX_DEGREE_EXCEEDED),
    ],
)
def test_invalid_generators_fail_only_at_contract_stage(
    tmp_path: Path,
    n: int,
    family: str,
    parameters: dict[str, object],
    stage: int,
    code: ErrorCode,
) -> None:
    config = generator_config(n, family, parameters)
    candidate = materialize_candidate(config, JsonStore(Workspace.open(tmp_path)))
    edge_validation = validate_edges(n, candidate.edge_data)
    if stage == 3:
        assert code in {item.code for item in edge_validation.result.errors}
    else:
        assert edge_validation.edges is not None
        structure = validate_linear_forest(n, edge_validation.edges)
        assert code in {item.code for item in structure.errors}


@pytest.mark.parametrize(
    ("n", "family", "parameters", "edge_count"),
    [
        (5, "empty", {}, 0),
        (6, "matching", {"edge_count": 3}, 3),
        (5, "single_path", {"edge_count": 4}, 4),
        (7, "multiple_paths", {"component_edge_lengths": [2, 1]}, 3),
    ],
)
def test_valid_generators_are_reproducible_and_valid(
    tmp_path: Path, n: int, family: str, parameters: dict[str, object], edge_count: int
) -> None:
    config = generator_config(n, family, parameters)
    store = JsonStore(Workspace.open(tmp_path))
    first = materialize_candidate(config, store)
    second = materialize_candidate(config, store)
    assert first == second
    assert len(first.edge_data) == edge_count
    edges = validate_edges(n, first.edge_data).edges
    assert edges is not None
    assert validate_linear_forest(n, edges).valid


@pytest.mark.parametrize(
    ("seed", "expected"),
    [
        (0, [[1, 4], [4, 3], [7, 2]]),
        (1, [[2, 4], [4, 6], [1, 7]]),
        (7, [[5, 2], [2, 4], [7, 3]]),
        (9_223_372_036_854_775_807, [[7, 2], [2, 5], [1, 3]]),
    ],
)
def test_builtin_v1_counter_and_golden_seed_vectors(seed: int, expected: list[list[int]]) -> None:
    config = generator_config(
        7,
        "multiple_paths",
        {"component_edge_lengths": [2, 1]},
        seed,
    )
    assert BUILTIN_V1_COUNTER_ASCII == b"0"
    assert generate_edges(config, config.source) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("n", "family", "parameters"),
    [
        (3, "matching", {"edge_count": 2}),
        (3, "single_path", {"edge_count": 3}),
        (4, "multiple_paths", {"component_edge_lengths": [2, 1]}),
        (2, "invalid_cycle", {"cycle_length": 3}),
        (3, "invalid_degree3", {}),
    ],
)
def test_impossible_generator_parameters_are_configuration_errors(
    n: int, family: str, parameters: dict[str, object]
) -> None:
    with pytest.raises(ValueError):
        generator_config(n, family, parameters)
