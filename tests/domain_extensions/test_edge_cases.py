from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from tesis_domain_extensions.application import DomainApplication
from tesis_domain_extensions.catalog import build_catalog, resolve_adapter
from tesis_domain_extensions.contracts.common import LargeNonNegativeInteger
from tesis_domain_extensions.contracts.projection import domain_experiment_id
from tesis_domain_extensions.domains.inspection_route.adapter import InspectionRouteAdapter
from tesis_domain_extensions.domains.inspection_route.contracts import (
    InspectionRouteConfig,
    InspectionRouteProjection,
    InspectionRouteProjectionContext,
)
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_domain_extensions.projection_store import ProjectionStore
from tesis_proyect.application.commands import CoreCommands
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode
from tests.domain_extensions.conftest import RUN_ID


def _interpret(
    report: dict[str, object],
    config: InspectionRouteConfig,
    context: InspectionRouteProjectionContext,
):
    case = next(InspectionRouteAdapter().iter_cases(config, context))
    return InspectionRouteAdapter().interpret(
        report,
        config,
        context,
        run_id=RUN_ID,
        domain_experiment_id=case.core_experiment_id,
        case=case,
    )


def test_common_contract_validators_reject_noncanonical_large_integers() -> None:
    adapter = TypeAdapter(LargeNonNegativeInteger)
    assert adapter.validate_python(0) == 0
    assert adapter.validate_python("9007199254740992") == "9007199254740992"
    for value in (True, -1, 9_007_199_254_740_992, "12", "01", 1.5):
        with pytest.raises(ValidationError):
            adapter.validate_python(value)


@pytest.mark.parametrize(
    ("code", "exit_code"),
    [
        (ErrorCode.NOT_FOUND, 66),
        (ErrorCode.RUN_CONTROL_UNAVAILABLE, 69),
        (ErrorCode.IO_ERROR, 74),
        (ErrorCode.RUN_ALREADY_ACTIVE, 75),
        (ErrorCode.CONFIG_INVALID, 78),
        (ErrorCode.SCHEMA_INVALID, 65),
        (ErrorCode.INTERNAL_ERROR, 70),
    ],
)
def test_domain_application_preserves_core_exit_categories(
    code: ErrorCode,
    exit_code: int,
) -> None:
    error = OperationalError(code, "failure")
    assert DomainApplication._core_exit_code(error) == exit_code
    assert DomainApplication._core_error(error).exit_code == exit_code


def test_projection_contract_rejects_identity_and_mapping_drift(
    partial_config: InspectionRouteConfig,
) -> None:
    context = InspectionRouteAdapter().project(partial_config).context
    base = {
        "schema_version": "1.0.0",
        "domain_experiment_id": domain_experiment_id(partial_config),
        "created_at": "2026-08-29T12:00:00.000Z",
        "domain_config": partial_config.model_dump(mode="json"),
        "projection_context": context.model_dump(mode="json"),
    }
    variants = []
    wrong_id = deepcopy(base)
    wrong_id["domain_experiment_id"] = "0" * 64
    variants.append(wrong_id)
    wrong_vertex = deepcopy(base)
    wrong_vertex["projection_context"]["vertex_mapping"][0]["vertex"] = 2
    variants.append(wrong_vertex)
    repeated = deepcopy(base)
    repeated["projection_context"]["vertex_mapping"][1]["location_id"] = "acceso"
    variants.append(repeated)
    for payload in variants:
        with pytest.raises((ValidationError, ValueError)):
            InspectionRouteProjection.model_validate(payload)


def test_catalog_rejects_invalid_shape_and_non_string_identity() -> None:
    class MissingIdentity:
        def project(self, config: object) -> object:
            return config

    with pytest.raises(ValueError, match="string id"):
        build_catalog((MissingIdentity(),))  # type: ignore[arg-type]
    for payload in (b"not-json", b"[]", b'{"domain":{"id":1,"version":"1.0.0"}}'):
        with pytest.raises(DomainExtensionError):
            resolve_adapter(payload)


def test_adapter_rejects_bom_and_invalid_contract() -> None:
    adapter = InspectionRouteAdapter()
    with pytest.raises(DomainExtensionError, match="BOM"):
        adapter.parse_config(b"\xef\xbb\xbf{}")
    with pytest.raises(DomainExtensionError, match="inválida"):
        adapter.parse_config(b"{}")


def test_prepare_creates_independent_projections_and_rejects_tampering(
    tmp_path: Path,
    partial_config: InspectionRouteConfig,
) -> None:
    (tmp_path / "experiments").mkdir()
    (tmp_path / "runs").mkdir()
    timestamps = iter(("2026-08-29T12:00:00.000Z", "2026-08-29T13:00:00.000Z"))
    store = ProjectionStore(
        tmp_path,
        CoreCommands.open(tmp_path),
        clock=lambda: next(timestamps),
    )
    adapter = InspectionRouteAdapter()
    first = store.prepare(adapter, partial_config)
    second = store.prepare(adapter, partial_config)
    assert second.record.created_at != first.record.created_at
    assert second.record.domain_experiment_id != first.record.domain_experiment_id

    path = tmp_path / "domain_projections" / f"{first.record.domain_experiment_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["projection_context"]["vertex_mapping"].reverse()
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DomainExtensionError, match=r"inválida|contexto"):
        store.load(first.record.domain_experiment_id)
    assert store.load(second.record.domain_experiment_id).record == second.record


def test_projection_store_rejects_symlink_roots(
    tmp_path: Path,
    partial_config: InspectionRouteConfig,
) -> None:
    (tmp_path / "experiments").mkdir()
    (tmp_path / "runs").mkdir()
    target = tmp_path / "target"
    target.mkdir()
    try:
        (tmp_path / "domain_projections").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(DomainExtensionError, match="directorio real"):
        ProjectionStore(tmp_path, CoreCommands.open(tmp_path)).prepare(
            InspectionRouteAdapter(), partial_config
        )


def test_interpretation_handles_skips_and_unknown_diagnostics(
    partial_config: InspectionRouteConfig,
    projection_context: InspectionRouteProjectionContext,
    success_report: dict[str, object],
) -> None:
    report = deepcopy(success_report)
    report["structure"] = None
    report["methods"] = {
        "exact": None,
        "reference": {
            "status": "skipped",
            "skip": {"code": "BRUTE_FORCE_LIMIT_EXCEEDED", "message": "limit"},
        },
    }
    report["comparison"] = None
    result = _interpret(report, partial_config, projection_context)
    assert result.feasibility == "inconclusive"
    assert result.route_count is None and result.technical_metrics is None
    assert result.limitations[0].code == "BRUTE_FORCE_LIMIT_EXCEEDED"

    report["diagnostics"] = [{"code": "UNEXPECTED_DOMAIN_ERROR"}]
    result = _interpret(report, partial_config, projection_context)
    assert result.feasibility == "invalid_constraints"


def test_interpretation_rejects_identity_structure_and_count_drift(
    partial_config: InspectionRouteConfig,
    projection_context: InspectionRouteProjectionContext,
    success_report: dict[str, object],
) -> None:
    variants = []
    for key, value in (("run_id", "other"), ("experiment_id", "other")):
        changed = deepcopy(success_report)
        changed[key] = value
        variants.append(changed)
    wrong_n = deepcopy(success_report)
    wrong_n["instance"]["n"] = 7  # type: ignore[index]
    variants.append(wrong_n)
    wrong_edges = deepcopy(success_report)
    wrong_edges["instance"]["edges"] = [[1, 3]]  # type: ignore[index]
    variants.append(wrong_edges)
    wrong_status = deepcopy(success_report)
    wrong_status["run_status"] = "running"
    variants.append(wrong_status)
    wrong_type = deepcopy(success_report)
    wrong_type["structure"]["case_type"] = "unknown"  # type: ignore[index]
    variants.append(wrong_type)
    wrong_comparison = deepcopy(success_report)
    wrong_comparison["comparison"] = {"status": "unknown"}
    variants.append(wrong_comparison)
    missing_examined = deepcopy(success_report)
    del missing_examined["methods"]["reference"]["metrics"]["candidates_examined"]  # type: ignore[index]
    variants.append(missing_examined)
    for report in variants:
        with pytest.raises(DomainExtensionError):
            _interpret(report, partial_config, projection_context)
