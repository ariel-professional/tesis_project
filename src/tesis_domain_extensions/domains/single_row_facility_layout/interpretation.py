from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, cast

from tesis_domain_extensions.adapters import ProjectedCase
from tesis_domain_extensions.contracts.common import MeasureDefinition, ProducerRef
from tesis_domain_extensions.contracts.results import (
    DomainDiagnostic,
    DomainLimitation,
    RouteCount,
    TechnicalMetrics,
)
from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
    LayoutCaseOrigin,
    LayoutCasePayload,
    LayoutForestResult,
    SingleRowFacilityLayoutConfig,
    SingleRowProjectionContext,
)
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_proyect.models.reports import ReportSummary

PRIMARY_MEASURE = MeasureDefinition(
    id="base-relative-layout-availability",
    name="Disponibilidad de disposiciones respecto del diseño base",
    definition=(
        "Fracción de disposiciones físicas lineales que continúan disponibles respecto "
        "del diseño base, identificando una fila y su reflejo."
    ),
)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise DomainExtensionError(f"El reporte del CORE no contiene {label} válido.")
    return cast(Mapping[str, object], value)


def _large(value: object, label: str) -> int | str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise DomainExtensionError(f"El reporte del CORE no contiene {label} válido.")
    return value


def _producer(method: Mapping[str, object]) -> ProducerRef:
    raw = _mapping(method.get("engine"), "engine")
    identifier = raw.get("id")
    version = raw.get("version")
    if not isinstance(identifier, str) or not isinstance(version, str):
        raise DomainExtensionError("El reporte del CORE no contiene un productor válido.")
    return ProducerRef(id=identifier, version=version)


def _count(  # noqa: C901 - comparison states are intentionally explicit
    report: Mapping[str, object],
) -> tuple[RouteCount | None, TechnicalMetrics | None]:
    methods = _mapping(report.get("methods"), "methods")
    successes: dict[str, Mapping[str, object]] = {}
    for name in ("exact", "reference"):
        raw = methods.get(name)
        if raw is not None:
            method = _mapping(raw, f"methods.{name}")
            if method.get("status") == "success":
                successes[name] = method
    comparison_status: Literal["match", "mismatch", "not_applicable"] | None = None
    raw_comparison = report.get("comparison")
    if raw_comparison is not None:
        status = _mapping(raw_comparison, "comparison").get("status")
        if status not in {"match", "mismatch", "not_applicable"}:
            raise DomainExtensionError("El CORE informó una comparación desconocida.")
        comparison_status = cast(Literal["match", "mismatch", "not_applicable"], status)
    if not successes:
        return None, None
    selected: Mapping[str, object] | None = None
    if comparison_status == "match" and len(successes) == 2:
        selected = successes["reference"]
    elif comparison_status == "not_applicable" and len(successes) == 1:
        selected = next(iter(successes.values()))
    convention_source = selected or next(iter(successes.values()))
    convention = convention_source.get("counting_convention")
    if convention != "undirected_paths_reverse_identified":
        raise DomainExtensionError("El reporte usa otra convención de conteo.")
    result = RouteCount(
        value=_large(selected.get("value"), "value") if selected is not None else None,
        method=_producer(selected) if selected is not None else None,
        exact_value=(
            _large(successes["exact"].get("value"), "exact.value") if "exact" in successes else None
        ),
        reference_value=(
            _large(successes["reference"].get("value"), "reference.value")
            if "reference" in successes
            else None
        ),
        counting_convention="undirected_paths_reverse_identified",
        comparison_status=comparison_status,
    )
    if selected is None:
        return result, None
    metrics = _mapping(selected.get("metrics"), "metrics")
    duration = metrics.get("duration_ms")
    examined = metrics.get("candidates_examined")
    if isinstance(duration, bool) or not isinstance(duration, int) or examined is None:
        return result, None
    return result, TechnicalMetrics(
        duration_ms=duration,
        candidates_examined=_large(examined, "candidates_examined"),
    )


def _limitations(report: Mapping[str, object]) -> list[DomainLimitation]:
    methods = _mapping(report.get("methods"), "methods")
    limitations: list[DomainLimitation] = []
    for name in ("exact", "reference"):
        raw = methods.get(name)
        if raw is None:
            continue
        method = _mapping(raw, f"methods.{name}")
        if method.get("status") != "skipped":
            continue
        skip = _mapping(method.get("skip"), "skip")
        code = skip.get("code")
        message = skip.get("message")
        if isinstance(code, str) and isinstance(message, str):
            limitations.append(DomainLimitation(code=code, message=message))
    return limitations


def interpret_case(  # noqa: C901 - identity, evidence and domain mapping stay together
    core_report: ReportSummary,
    config: SingleRowFacilityLayoutConfig,
    context: SingleRowProjectionContext,
    case: ProjectedCase,
    *,
    run_id: str,
    core_experiment_id: str,
) -> LayoutForestResult:
    report = core_report.model_dump(mode="json")
    if report.get("run_id") != run_id or report.get("experiment_id") != core_experiment_id:
        raise DomainExtensionError("El reporte del CORE pertenece a otro caso.")
    payload = cast(LayoutCasePayload, case.payload)
    origin = cast(LayoutCaseOrigin, case.origin)
    instance = report.get("instance")
    if instance is not None:
        view = _mapping(instance, "instance")
        if view.get("n") != len(config.study.stations):
            raise DomainExtensionError("La cantidad de vértices no coincide con el estudio.")
        expected = case.core_config.source.model_dump(mode="json")["edges"]
        if view.get("edges") != expected:
            raise DomainExtensionError("Las aristas del CORE no coinciden con el caso generado.")
    diagnostics: list[DomainDiagnostic] = []
    raw_diagnostics = report.get("diagnostics")
    if isinstance(raw_diagnostics, list):
        for raw in raw_diagnostics:
            code = _mapping(raw, "diagnostic").get("code")
            if isinstance(code, str):
                diagnostics.append(
                    DomainDiagnostic(
                        core_code=code,
                        message="El CORE rechazó un caso que el dominio había prevalidado.",
                        affected_locations=[],
                    )
                )
    count, metrics = _count(report)
    status = report.get("run_status")
    if diagnostics:
        feasibility: Literal["feasible", "invalid_constraints", "inconclusive"] = (
            "invalid_constraints"
        )
    elif count is not None and count.value is not None:
        feasibility = "feasible"
    else:
        feasibility = "inconclusive"
    if status not in {"completed", "failed", "cancelled"}:
        raise DomainExtensionError("La interpretación requiere un run terminal.")
    return LayoutForestResult(
        forest_id=case.case_id,
        origins=[origin],
        edges=payload.edges,
        core_run_id=run_id,
        feasibility=feasibility,
        compatible_layout_count=count,
        technical_metrics=metrics,
        diagnostics=diagnostics,
        limitations=_limitations(report),
    )
