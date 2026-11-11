import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tesis_proyect.domain.analysis import analyze_linear_forest, validate_analysis_integrity
from tesis_proyect.domain.hashing import canonical_json_bytes, instance_hash, run_config_hash
from tesis_proyect.domain.validation import validate_edges, validate_linear_forest
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import ErrorCode


@pytest.mark.parametrize(
    ("n", "raw", "code"),
    [
        (4, [[1, 2, 3]], ErrorCode.MALFORMED_EDGE),
        (4, [[1, "a"]], ErrorCode.MALFORMED_EDGE),
        (4, [[1, 1]], ErrorCode.LOOP_EDGE),
        (5, [[1, 6]], ErrorCode.VERTEX_OUT_OF_RANGE),
        (4, [[1, 2], [2, 1]], ErrorCode.DUPLICATE_EDGE),
    ],
)
def test_edge_diagnostics_at_stage_three(n: int, raw: list[object], code: ErrorCode) -> None:
    validation = validate_edges(n, raw)
    assert validation.edges is None
    assert code in {item.code for item in validation.result.errors}


def test_collects_all_detectable_edge_diagnostics_in_stable_order() -> None:
    raw = [[1, 1], [1, 5], [2, 1], [1, 2], [True, 2]]
    result = validate_edges(4, raw).result
    assert [item.code for item in result.errors] == [
        ErrorCode.MALFORMED_EDGE,
        ErrorCode.LOOP_EDGE,
        ErrorCode.DUPLICATE_EDGE,
        ErrorCode.VERTEX_OUT_OF_RANGE,
    ]


@pytest.mark.parametrize(
    ("n", "raw", "code"),
    [
        (3, [[1, 2], [2, 3], [1, 3]], ErrorCode.CYCLE_DETECTED),
        (5, [[1, 2], [1, 3], [1, 4]], ErrorCode.MAX_DEGREE_EXCEEDED),
    ],
)
def test_structure_diagnostics_at_stage_four(n: int, raw: list[list[int]], code: ErrorCode) -> None:
    edges = validate_edges(n, raw).edges
    assert edges is not None
    result = validate_linear_forest(n, edges)
    assert not result.valid
    assert code in {item.code for item in result.errors}


@pytest.mark.parametrize(
    ("n", "raw", "lengths", "free", "case_type"),
    [
        (1, [], [], [1], "empty"),
        (4, [[2, 1], [4, 3]], [1, 1], [], "matching"),
        (5, [[3, 2], [4, 3], [2, 1]], [3], [5], "single_path"),
        (6, [[2, 3], [1, 2], [5, 4]], [2, 1], [6], "multiple_paths"),
    ],
)
def test_analysis_is_canonical(
    n: int,
    raw: list[list[int]],
    lengths: list[int],
    free: list[int],
    case_type: str,
) -> None:
    edges = validate_edges(n, raw).edges
    assert edges is not None
    assert validate_linear_forest(n, edges).valid
    analysis = analyze_linear_forest(n, edges)
    assert analysis.component_lengths == lengths
    assert analysis.free_vertices == free
    assert analysis.case_type == case_type
    for component in analysis.components:
        assert component.vertices <= list(reversed(component.vertices))


@pytest.mark.parametrize(
    ("n", "raw", "case_type"),
    [
        (4, [], "empty"),
        (5, [[1, 2], [2, 3], [3, 4], [4, 5]], "hamiltonian_path_extreme"),
        (2, [[1, 2]], "hamiltonian_path_extreme"),
        (4, [[1, 2]], "single_edge"),
        (5, [[1, 2], [3, 4]], "matching"),
        (5, [[1, 2], [2, 3]], "single_path"),
        (6, [[1, 2], [2, 3], [4, 5]], "multiple_paths"),
    ],
)
def test_six_case_types_follow_precedence(n: int, raw: list[list[int]], case_type: str) -> None:
    edges = validate_edges(n, raw).edges
    assert edges is not None
    analysis = analyze_linear_forest(n, edges)
    assert analysis.case_type == case_type
    assert validate_analysis_integrity(n, edges, analysis)
    assert not validate_analysis_integrity(
        n,
        edges,
        analysis.model_copy(update={"blocks": analysis.blocks + 1}),
    )


@given(
    n=st.integers(min_value=2, max_value=100),
    u=st.integers(min_value=1, max_value=100),
    v=st.integers(min_value=1, max_value=100),
)
def test_orientation_does_not_change_normalized_edge_or_hash(n: int, u: int, v: int) -> None:
    u = (u - 1) % n + 1
    v = (v - 1) % n + 1
    if u == v:
        return
    first = validate_edges(n, [[u, v]]).edges
    second = validate_edges(n, [[v, u]]).edges
    assert first == second
    assert first is not None
    assert instance_hash(n, first) == instance_hash(n, second)


def test_instance_hash_excludes_provenance_and_schema_by_construction() -> None:
    assert instance_hash(4, ((1, 2),)) == instance_hash(4, ((1, 2),))
    assert instance_hash(4, ((1, 2),)) != instance_hash(4, ((1, 3),))


def _file_config(path: str) -> ExperimentConfig:
    from tests.contracts.test_foundation import valid_config

    data = valid_config()
    data["source"] = {"kind": "file", "path": path}
    return ExperimentConfig.model_validate(data)


def test_run_config_hash_normalizes_unicode_and_has_no_newline() -> None:
    composed = "données.json"
    decomposed = unicodedata.normalize("NFD", composed)
    assert run_config_hash(_file_config(composed)) == run_config_hash(_file_config(decomposed))
    assert not canonical_json_bytes({"b": 2, "a": 1}).endswith(b"\n")
    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'


def test_run_config_hash_preserves_opaque_inline_unicode() -> None:
    from tests.contracts.test_foundation import valid_config

    composed = "é"
    decomposed = unicodedata.normalize("NFD", composed)
    first = valid_config()
    first["source"] = {"kind": "inline", "edges": [[1, {composed: composed}]]}
    second = valid_config()
    second["source"] = {"kind": "inline", "edges": [[1, {decomposed: decomposed}]]}
    first_model = ExperimentConfig.model_validate(first)
    second_model = ExperimentConfig.model_validate(second)
    assert first_model.source != second_model.source
    assert run_config_hash(first_model) != run_config_hash(second_model)


@pytest.mark.parametrize("value", [1.0, float("nan"), float("inf")])
def test_hash_canonicalization_rejects_floats(value: float) -> None:
    with pytest.raises(ValueError):
        canonical_json_bytes({"value": value})
