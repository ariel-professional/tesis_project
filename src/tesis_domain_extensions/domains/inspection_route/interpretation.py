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
from tesis_domain_extensions.domains.inspection_route.contracts import (
    InspectionConstraintPayload,
    InspectionConstraintSetResult,
    InspectionRouteConfig,
    InspectionRouteProjectionContext,
    InspectionScenarioOrigin,
    InspectionStructure,
)
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_proyect.models.reports import ReportSummary

PRIMARY_MEASURE = MeasureDefinition(
    id="retained-route-flexibility",
    name="Flexibilidad de recorridos conservada",
    definition=(
        "Fracción de recorridos físicos admisibles respecto de los recorridos "
        "sin obligaciones de consecutividad."
    ),
)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise DomainExtensionError(f"El reporte del CORE no contiene {label} válido.")
    return cast(Mapping[str, object], value)


def _items(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise DomainExtensionError(f"El reporte del CORE no contiene {label} válido.")
    return cast(list[object], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise DomainExtensionError(f"El reporte del CORE no contiene {label} válido.")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainExtensionError(f"El reporte del CORE no contiene {label} válido.")
    return value


def _large_integer(value: object, label: str) -> int | str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise DomainExtensionError(f"El reporte del CORE no contiene {label} válido.")
    return value


def _structure(
    report: Mapping[str, object],
    vertex_to_location: Mapping[int, str],
) -> InspectionStructure | None:
    raw = report.get("structure")
    if raw is None:
        return None
    view = _mapping(raw, "structure")
    chains: list[list[str]] = []
    for component in _items(view.get("components"), "structure.components"):
        component_view = _mapping(component, "component")
        chains.append(
            [
                vertex_to_location[_integer(vertex, "component vertex")]
                for vertex in _items(component_view.get("vertices"), "component.vertices")
            ]
        )
    free = [
        vertex_to_location[_integer(vertex, "free vertex")]
        for vertex in _items(view.get("free_vertices"), "structure.free_vertices")
    ]
    raw_case_type = _text(view.get("case_type"), "structure.case_type")
    allowed_case_types = {
        "empty",
        "hamiltonian_path_extreme",
        "single_edge",
        "matching",
        "single_path",
        "multiple_paths",
    }
    if raw_case_type not in allowed_case_types:
        raise DomainExtensionError("El CORE informó un tipo de caso desconocido.")
    return InspectionStructure(
        core_case_type=cast(
            Literal[
                "empty",
                "hamiltonian_path_extreme",
                "single_edge",
                "matching",
                "single_path",
                "multiple_paths",
            ],
            raw_case_type,
        ),
        mandatory_chains=chains,
        unconstrained_locations=free,
        planning_blocks=_integer(view.get("blocks"), "structure.blocks"),
    )


def _diagnostics(report: Mapping[str, object]) -> list[DomainDiagnostic]:
    translated: list[DomainDiagnostic] = []
    for raw in _items(report.get("diagnostics"), "diagnostics"):
        code = _text(_mapping(raw, "diagnostic").get("code"), "diagnostic.code")
        translated.append(
            DomainDiagnostic(
                core_code=code,
                message="El CORE rechazó un escenario que el dominio había prevalidado.",
                affected_locations=[],
            )
        )
    return translated


def _count_and_metrics(  # noqa: C901 - comparison states are intentionally explicit
    report: Mapping[str, object],
) -> tuple[RouteCount | None, TechnicalMetrics | None]:
    methods = _mapping(report.get("methods"), "methods")
    successes: dict[str, Mapping[str, object]] = {}
    for method_name in ("exact", "reference"):
        raw_method = methods.get(method_name)
        if raw_method is None:
            continue
        method = _mapping(raw_method, f"methods.{method_name}")
        if method.get("status") == "success":
            successes[method_name] = method
    comparison = report.get("comparison")
    comparison_status: Literal["match", "mismatch", "not_applicable"] | None = None
    if comparison is not None:
        raw_status = _text(_mapping(comparison, "comparison").get("status"), "comparison.status")
        if raw_status not in {"match", "mismatch", "not_applicable"}:
            raise DomainExtensionError("El CORE informó una comparación desconocida.")
        comparison_status = cast(Literal["match", "mismatch", "not_applicable"], raw_status)
    selected: Mapping[str, object] | None = None
    selected_name: str | None = None
    if comparison_status == "match" and len(successes) == 2:
        selected_name, selected = "reference", successes["reference"]
    elif comparison_status == "not_applicable" and len(successes) == 1:
        selected_name, selected = next(iter(successes.items()))
    if not successes:
        return None, None
    engine = _mapping(selected.get("engine"), "method.engine") if selected is not None else None
    route_count = RouteCount(
        value=_large_integer(selected.get("value"), "method.value")
        if selected is not None
        else None,
        method=(
            ProducerRef(
                id=_text(engine.get("id"), "engine.id"),
                version=_text(engine.get("version"), "engine.version"),
            )
            if engine is not None
            else None
        ),
        exact_value=(
            _large_integer(successes["exact"].get("value"), "exact.value")
            if "exact" in successes
            else None
        ),
        reference_value=(
            _large_integer(successes["reference"].get("value"), "reference.value")
            if "reference" in successes
            else None
        ),
        counting_convention=cast(
            Literal["undirected_paths_reverse_identified"],
            _text(
                (selected or next(iter(successes.values()))).get("counting_convention"),
                "counting_convention",
            ),
        ),
        comparison_status=comparison_status,
    )
    if selected is None:
        return route_count, None
    metrics_view = _mapping(selected.get("metrics"), "method.metrics")
    examined = metrics_view.get("candidates_examined")
    if examined is None:
        if selected_name == "reference":
            raise DomainExtensionError("El conteo seleccionado no informa candidatos examinados.")
        return route_count, None
    return route_count, TechnicalMetrics(
        duration_ms=_integer(metrics_view.get("duration_ms"), "metrics.duration_ms"),
        candidates_examined=_large_integer(examined, "metrics.candidates_examined"),
    )


def _limitations(report: Mapping[str, object]) -> list[DomainLimitation]:
    methods = _mapping(report.get("methods"), "methods")
    result: list[DomainLimitation] = []
    for method_name in ("exact", "reference"):
        raw_method = methods.get(method_name)
        if raw_method is None:
            continue
        method = _mapping(raw_method, f"methods.{method_name}")
        if method.get("status") != "skipped":
            continue
        skip = _mapping(method.get("skip"), f"methods.{method_name}.skip")
        code = _text(skip.get("code"), "skip.code")
        if code == "EXACT_ENGINE_NOT_AVAILABLE":
            message = "El método exacto propuesto todavía no está disponible."
        elif code == "BRUTE_FORCE_LIMIT_EXCEEDED":
            message = "El escenario supera el límite configurado para el método de referencia."
        else:
            message = _text(skip.get("message"), "skip.message")
        result.append(DomainLimitation(code=code, message=message))
    return result


def interpret_case(
    core_report: ReportSummary | Mapping[str, object],
    config: InspectionRouteConfig,
    context: InspectionRouteProjectionContext,
    case: ProjectedCase,
    *,
    run_id: str,
    core_experiment_id: str,
) -> InspectionConstraintSetResult:
    report = (
        core_report.model_dump(mode="json")
        if isinstance(core_report, ReportSummary)
        else dict(core_report)
    )
    if report.get("schema_version") != "1.0.0":
        raise DomainExtensionError("La versión del reporte del CORE no está soportada.")
    if report.get("run_id") != run_id or report.get("experiment_id") != core_experiment_id:
        raise DomainExtensionError("El reporte del CORE pertenece a otro escenario.")
    instance = report.get("instance")
    if instance is not None:
        instance_view = _mapping(instance, "instance")
        if instance_view.get("n") != len(config.study.locations):
            raise DomainExtensionError("La cantidad de vértices no coincide con el estudio.")
        expected = case.core_config.source.model_dump(mode="json")["edges"]
        if instance_view.get("edges") != expected:
            raise DomainExtensionError("Las aristas del CORE no coinciden con el escenario.")
    raw_status = report.get("run_status")
    if raw_status not in {"completed", "failed", "cancelled"}:
        raise DomainExtensionError("La interpretación requiere un run terminal.")
    diagnostics = _diagnostics(report)
    count, metrics = _count_and_metrics(report)
    if diagnostics:
        feasibility: Literal["feasible", "invalid_constraints", "inconclusive"] = (
            "invalid_constraints"
        )
    elif count is not None and count.value is not None:
        feasibility = "feasible"
    else:
        feasibility = "inconclusive"
    vertex_to_location = {item.vertex: item.location_id for item in context.vertex_mapping}
    payload = cast(InspectionConstraintPayload, case.payload)
    origin = cast(InspectionScenarioOrigin, case.origin)
    return InspectionConstraintSetResult(
        constraint_set_id=case.case_id,
        origins=[origin],
        required_consecutive_visits=payload.required_consecutive_visits,
        core_run_id=run_id,
        feasibility=feasibility,
        structure=_structure(report, vertex_to_location),
        route_count=count,
        technical_metrics=metrics,
        diagnostics=diagnostics,
        limitations=_limitations(report),
    )
