from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import nullcontext
from fractions import Fraction
from pathlib import Path
from time import monotonic
from typing import Any, cast

from tesis_domain_extensions.adapters import CaseGenerationStatistics
from tesis_domain_extensions.contracts.common import ProducerRef, large_non_negative_integer
from tesis_domain_extensions.contracts.results import RouteCount
from tesis_domain_extensions.domains.single_row_facility_layout.analysis import (
    _forest_structure,
    decision_case_id,
)
from tesis_domain_extensions.domains.single_row_facility_layout.analysis_v2 import _findings
from tesis_domain_extensions.domains.single_row_facility_layout.contracts import (
    SingleRowProjectionContext,
)
from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v21 import (
    FastDesignSummaryV21,
    FastResultSummaryV21,
    LayoutCaseResultV21,
    SingleRowFacilityLayoutConfigV21,
)
from tesis_domain_extensions.domains.single_row_facility_layout.fast_result_store import (
    FastResultWriter,
)
from tesis_domain_extensions.domains.single_row_facility_layout.generation import (
    LinearForestGenerator,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.catalog import (
    selected_objective_snapshots,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.contracts import (
    ParetoClassification,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.evaluators import (
    evaluate_adjacency_flow,
    evaluate_adjacency_value,
    evaluate_rel_closeness,
    evaluate_retained_layouts,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.pareto import (
    Direction,
    ParetoPoint,
)
from tesis_domain_extensions.errors import DomainExtensionError, DomainRunCancelled
from tesis_proyect.application.fast_counting import FastCountingWorker, FastWorkerCancelled

COUNTING_PRODUCER = ProducerRef(id="linear-forest-closed-form", version="1")


def query_fast_result(  # noqa: C901 - command-specific validation stays next to index access
    application: Any, manifest: Any, adapter: Any, operation: str, params: Any
) -> Any:
    result = application.store.load_domain_result(manifest.domain_run_id, adapter)
    if not isinstance(result, FastResultSummaryV21):
        raise DomainExtensionError(
            "El resumen confirmado no es compatible con consultas indexadas."
        )
    with nullcontext(application.fast_result_reader(manifest)) as reader:
        designs = {item.design_id: item for item in result.designs}
        if operation == "plot_projection":
            from tesis_domain_extensions.domains.single_row_facility_layout.plot_projection import (
                ProjectionRequest,
                build_projection,
            )

            request = ProjectionRequest(
                design_id=str(params["design_id"]),
                x_objective_id=str(params["x_objective_id"]),
                y_objective_id=str(params["y_objective_id"]),
                x_scale=cast(Any, params["x_scale"]),
                y_scale=cast(Any, params["y_scale"]),
                x_log_k=float(params["x_log_k"]),
                y_log_k=float(params["y_log_k"]),
            )
            design = designs.get(request.design_id)
            if design is None:
                raise DomainExtensionError("El diseño no pertenece al resultado confirmado.")
            cache_key = (str(manifest.domain_run_id), *request.cache_key)
            cached = application._fast_result_plot_projection_cache
            if cached is None or cached[0] != cache_key:
                projection = build_projection(reader, design, request)
                application._fast_result_plot_projection_cache = (cache_key, projection)
            else:
                projection = cached[1]
            return projection.page(
                section=cast(Any, params["section"]),
                level=int(params["level"]),
                cursor=int(params.get("cursor", 0)),
            )
        if operation == "case_detail":
            case = reader.find_case(str(params["case_id"]))
            total, equivalents = reader.equivalent_page(
                str(case["forest_id"]), int(params.get("equivalent_offset", 0))
            )
            offset = int(params.get("equivalent_offset", 0))
            return {
                "case": case,
                "equivalents": equivalents,
                "equivalent_count": total,
                "next_offset": offset + len(equivalents)
                if offset + len(equivalents) < total
                else None,
            }
        target = reader.find_case(str(params["case_id"])) if operation == "dominators" else None
        design_id = str(params.get("design_id", ""))
        if target is not None:
            design_id = str(target.get("design_id", ""))
        design = designs.get(design_id)
        if design is None:
            raise DomainExtensionError("El diseño no pertenece al resultado confirmado.")
        if operation == "case_page":
            order = str(params["order"])
            index = design.order_indexes.get(order)
            if index is None:
                raise DomainExtensionError("El orden solicitado no está disponible.")
            page = int(params["page"])
            items = reader.page(index, page, reverse=params.get("direction") == "descending")
            return {
                "design_id": design.design_id,
                "order": order,
                "direction": params.get("direction", "ascending"),
                "page": page,
                "page_size": 50,
                "total": reader.index_count(index),
                "items": items,
            }
        if operation == "frontier":
            if design.frontier_index is None:
                return {"design_id": design.design_id, "items": [], "next_cursor": None}
            cursor = int(params.get("cursor", 0))
            items = reader.page(design.frontier_index, cursor, page_size=50)
            total = reader.index_count(design.frontier_index)
            return {
                "design_id": design.design_id,
                "items": items,
                "next_cursor": cursor + 1 if (cursor + 1) * 50 < total else None,
            }
        if operation == "plot_points":
            x_key, y_key = str(params["x_objective_id"]), str(params["y_objective_id"])
            ids = {item.definition.id for item in result.objective_snapshots}
            if x_key not in ids or y_key not in ids:
                raise DomainExtensionError("El objetivo solicitado no está disponible.")
            cursor = int(params.get("cursor", 0))
            cases = reader.page(design.order_indexes["case"], cursor, page_size=50)
            total = reader.index_count(design.order_indexes["case"])
            points = [
                {
                    "case_id": case["case_id"],
                    "x": case.get("criteria_vector", {}).get(x_key),
                    "y": case.get("criteria_vector", {}).get(y_key),
                }
                for case in cases
            ]
            return {
                "design_id": design.design_id,
                "points": points,
                "next_cursor": cursor + 1 if (cursor + 1) * 50 < total else None,
            }
        if operation == "dominators":
            assert target is not None
            target_values = target.get("criteria_vector", {})
            directions = {
                item.definition.id: item.definition.direction for item in result.objective_snapshots
            }
            cursor = int(params.get("cursor", 0))
            index = design.frontier_index
            if index is None:
                return {"items": [], "next_cursor": None}
            candidates = reader.page(index, cursor, page_size=50)
            matches = []
            for candidate in candidates:
                if candidate.get("case_id") == target.get("case_id"):
                    continue
                better = all(
                    (
                        Fraction(
                            candidate["criteria_vector"][key]["numerator"],
                            candidate["criteria_vector"][key]["denominator"],
                        )
                        <= Fraction(
                            target_values[key]["numerator"], target_values[key]["denominator"]
                        )
                    )
                    if directions[key] == "minimize"
                    else (
                        Fraction(
                            candidate["criteria_vector"][key]["numerator"],
                            candidate["criteria_vector"][key]["denominator"],
                        )
                        >= Fraction(
                            target_values[key]["numerator"], target_values[key]["denominator"]
                        )
                    )
                    for key in target_values
                )
                strict = any(
                    candidate["criteria_vector"][key] != target_values[key] for key in target_values
                )
                if better and strict:
                    differences = {}
                    for key in target_values:
                        preferred = Fraction(
                            candidate["criteria_vector"][key]["numerator"],
                            candidate["criteria_vector"][key]["denominator"],
                        )
                        observed = Fraction(
                            target_values[key]["numerator"],
                            target_values[key]["denominator"],
                        )
                        if preferred != observed:
                            delta = preferred - observed
                            differences[key] = {
                                "numerator": delta.numerator,
                                "denominator": delta.denominator,
                            }
                    matches.append({**candidate, "differences": differences})
            total = reader.index_count(index)
            return {
                "items": matches,
                "next_cursor": cursor + 1 if (cursor + 1) * 50 < total else None,
            }
    raise DomainExtensionError("Consulta de resultado desconocida.")


def evaluate_fast_cases(  # noqa: C901 - ordered pipeline keeps the single generator pass explicit
    config: SingleRowFacilityLayoutConfigV21,
    context: SingleRowProjectionContext,
    *,
    domain_experiment_id: str,
    run_directory: Path,
    timeout_ms: int,
    is_cancel_requested: Callable[[], bool],
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[
    dict[str, dict[str, int | str]],
    dict[str, int],
    dict[str, list[int]],
    dict[str, int],
    dict[str, int],
    dict[str, int],
]:
    """Generate and persist each valid case once, counting through one worker."""

    generator = LinearForestGenerator(
        cast(Any, config),
        cast(Any, context),
        is_cancel_requested=is_cancel_requested,
        collect_invalid_details=False,
    )
    cache: dict[tuple[int, int, int], int] = {}
    base_counts: dict[str, int] = {}
    valid_by_design = {design.id: 0 for design in config.study.designs}
    station_ids = [item.id for item in config.study.stations]
    components = {item.id: item for item in config.study.components}
    snapshots = selected_objective_snapshots(config.decision_model)
    directions = {item.definition.id: item.definition.direction for item in snapshots}
    points_by_design: dict[str, list[ParetoPoint]] = {
        design.id: [] for design in config.study.designs
    }
    vectors_complete: dict[str, bool] = {design.id: True for design in config.study.designs}
    total = sum(
        1 << (len(components) - len(design.base_component_ids)) for design in config.study.designs
    )
    processed = 0
    with (
        FastResultWriter(run_directory) as writer,
        FastCountingWorker(
            timeout_ms=timeout_ms, is_cancel_requested=is_cancel_requested
        ) as worker,
    ):
        for generated in generator:
            if is_cancel_requested():
                raise InterruptedError("fast domain run cancelled")
            origin = generated.origin
            n = len(station_ids)
            m = generated.edge_count
            c = generated.edge_component_count
            count_key = (n, c, m)
            if count_key not in cache:
                count = worker.count(*count_key)
                cache[count_key] = count
            else:
                count = cache[count_key]
            if not origin.added_component_ids:
                base_counts[origin.design_id] = count

            edges = list(generated.payload.edges)
            retained = (
                evaluate_retained_layouts(count, base_counts.get(origin.design_id))
                if config.decision_model.retained_compatible_layouts
                else None
            )
            rel = (
                list(evaluate_rel_closeness(config.decision_model.rel_closeness, edges).values())
                if config.decision_model.rel_closeness is not None
                else []
            )
            flow_input = config.decision_model.adjacency_flow
            flow = (
                evaluate_adjacency_flow(flow_input, edges)
                if flow_input is not None and not isinstance(flow_input, list)
                else None
            )
            adjacency_values = (
                [evaluate_adjacency_value(matrix, edges) for matrix in flow_input]
                if isinstance(flow_input, list)
                else []
            )
            route_count = RouteCount(
                value=large_non_negative_integer(count),
                method=COUNTING_PRODUCER,
                exact_value=large_non_negative_integer(count),
                reference_value=None,
                counting_convention="undirected_paths_reverse_identified",
                comparison_status="not_applicable",
            )
            draft = LayoutCaseResultV21(
                case_id=decision_case_id(
                    domain_experiment_id, origin.design_id, origin.added_component_ids
                ),
                forest_id=generated.forest_id,
                design_id=origin.design_id,
                mandatory_component_ids=list(
                    next(
                        item.base_component_ids
                        for item in config.study.designs
                        if item.id == origin.design_id
                    )
                ),
                added_component_ids=list(origin.added_component_ids),
                component_ids=[
                    *next(
                        item.base_component_ids
                        for item in config.study.designs
                        if item.id == origin.design_id
                    ),
                    *origin.added_component_ids,
                ],
                edges=edges,
                forest_structure=_forest_structure(station_ids, edges),
                prescribed_edge_count=m,
                core_run_id=None,
                feasibility="feasible",
                compatible_layout_count=route_count,
                retained_layouts=retained,
                rel_closeness=rel,
                captured_flow=flow,
                adjacency_values=adjacency_values,
                findings=_findings(cast(Any, config), edges),
                pareto_classification=ParetoClassification(
                    status="inconclusive",
                    objective_refs=[item.definition.id for item in snapshots],
                    dominated=None,
                    pareto_optimal=None,
                ),
                technical_metrics=None,
                diagnostics=[],
                limitations=[],
                counting_producer=COUNTING_PRODUCER,
                scientific_status="conclusive",
            )
            vector = _criteria_vector(draft)
            record = draft.model_dump(mode="json")
            record["criteria_vector"] = {
                name: {"numerator": value.numerator, "denominator": value.denominator}
                for name, value in vector.items()
            }
            ordinal = writer.append_case(record)
            valid_by_design[origin.design_id] += 1
            if draft.feasibility == "feasible":
                if set(vector) != set(directions):
                    vectors_complete[origin.design_id] = False
                else:
                    points_by_design[origin.design_id].append(ParetoPoint(str(ordinal), vector))
            processed += 1
            if on_progress is not None:
                on_progress(processed, total)
        frontiers: dict[str, list[int]] = {}
        for design_index, design in enumerate(config.study.designs):
            design_points = points_by_design[design.id]
            complete = bool(design_points) and vectors_complete[design.id]
            frontier = (
                sorted(int(item) for item in classify_fast_frontier(design_points, directions))
                if complete
                else []
            )
            if complete:
                frontiers[design.id] = frontier
                writer.write_ordinal_index(f"frontier/design-{design_index}.u64", frontier)
            for order_name, order_values in _design_order_keys(
                writer,
                design.id,
                directions,
            ):
                writer.write_sorted_ordinal_index(
                    f"orders/design-{design_index}-{order_name}.u64", order_values
                )
        artifacts = writer.finalize()
    invalid_by_design = {design.id: 0 for design in config.study.designs}
    for conflict in generator.conflict_summaries():
        invalid_by_design[conflict.design_id] += conflict.combination_count
    stats = {
        "theoretical_combinations": total,
        "valid_selections": processed,
        "invalid_combinations": generator.statistics.invalid_combinations,
        "forbidden_combinations": generator.statistics.forbidden_combinations,
        "cycle_pruned_branches": generator.statistics.cycle_pruned_branches,
        "degree_pruned_branches": generator.statistics.degree_pruned_branches,
        "unique_count_requests": len(cache),
        "cached_count_reuses": processed - len(cache),
        "pareto_complete_designs": len(frontiers),
    }
    return artifacts, stats, frontiers, base_counts, valid_by_design, invalid_by_design


def _design_order_keys(
    writer: FastResultWriter,
    design_id: str,
    directions: dict[str, Direction],
) -> Iterator[tuple[str, Iterator[tuple[tuple[Any, ...], int]]]]:
    def keyed(field: str) -> Iterator[tuple[tuple[Any, ...], int]]:
        for ordinal, case in writer.iter_appended_cases():
            if case.get("design_id") != design_id:
                continue
            if field == "case":
                key: tuple[Any, ...] = (str(case["case_id"]),)
            elif field == "components":
                components = tuple(str(item) for item in case["component_ids"])
                key = (len(components), components)
            elif field.startswith("criterion-"):
                objective_id = field.removeprefix("criterion-")
                fraction = writer.exact_fraction(case, objective_id)
                key = (fraction is None, fraction or Fraction(0))
            else:
                raise ValueError(f"unknown fast order {field}")
            yield key, ordinal

    yield "case", keyed("case")
    yield "components", keyed("components")
    for objective_id in directions:
        yield f"criterion-{objective_id}", keyed(f"criterion-{objective_id}")


def _criteria_vector(case: LayoutCaseResultV21) -> dict[str, Fraction]:
    vector: dict[str, Fraction] = {}
    if case.retained_layouts and case.retained_layouts.status == "conclusive":
        value = case.retained_layouts.fraction
        if value is not None:
            vector[case.retained_layouts.objective_id] = Fraction(
                int(value.numerator), int(value.denominator)
            )
    for result in case.rel_closeness:
        if result.status == "conclusive":
            vector[result.objective_id] = Fraction(
                int(result.fraction.numerator), int(result.fraction.denominator)
            )
    if (
        case.captured_flow is not None
        and case.captured_flow.status == "conclusive"
        and case.captured_flow.total is not None
    ):
        vector[case.captured_flow.objective_id] = Fraction(case.captured_flow.total)
    for adjacency_result in case.adjacency_values:
        if adjacency_result.status == "conclusive" and adjacency_result.total is not None:
            vector[adjacency_result.objective_id] = Fraction(adjacency_result.total)
    return vector


def classify_fast_frontier(  # noqa: C901 - dimension-specific algorithms avoid quadratic scans
    points: list[ParetoPoint], directions: dict[str, Direction]
) -> set[str]:
    """Return all frontier IDs without constructing per-case dominator lists."""

    if not points:
        return set()
    dimensions = tuple(directions)
    if any(set(point.values) != set(dimensions) for point in points):
        return set()

    def normalized(point: ParetoPoint) -> tuple[Fraction, ...]:
        return tuple(
            point.values[key] if directions[key] == "maximize" else -point.values[key]
            for key in dimensions
        )

    if len(dimensions) == 1:
        best = max(normalized(point)[0] for point in points)
        return {point.case_id for point in points if normalized(point)[0] == best}
    if len(dimensions) == 2:
        ordered = sorted(
            ((normalized(point), point.case_id) for point in points),
            key=lambda item: (-item[0][0], -item[0][1], item[1]),
        )
        frontier: set[str] = set()
        best_second: Fraction | None = None
        index = 0
        while index < len(ordered):
            vector = ordered[index][0]
            end = index + 1
            while end < len(ordered) and ordered[end][0] == vector:
                end += 1
            if best_second is None or vector[1] > best_second:
                frontier.update(identifier for _, identifier in ordered[index:end])
            if best_second is None or vector[1] > best_second:
                best_second = vector[1]
            index = end
        return frontier

    frontier_vectors: list[tuple[Fraction, ...]] = []
    frontier_ids: list[set[str]] = []
    for point in points:
        vector = normalized(point)
        if any(
            all(left >= right for left, right in zip(candidate, vector, strict=True))
            and candidate != vector
            for candidate in frontier_vectors
        ):
            continue
        dominated_indices = [
            index
            for index, candidate in enumerate(frontier_vectors)
            if all(left >= right for left, right in zip(vector, candidate, strict=True))
            and vector != candidate
        ]
        for index in reversed(dominated_indices):
            frontier_vectors.pop(index)
            frontier_ids.pop(index)
        if vector in frontier_vectors:
            frontier_ids[frontier_vectors.index(vector)].add(point.case_id)
        else:
            frontier_vectors.append(vector)
            frontier_ids.append({point.case_id})
    return set().union(*frontier_ids) if frontier_ids else set()


def execute_fast_run(
    application: Any,
    loaded: Any,
    manifest: Any,
) -> tuple[FastResultSummaryV21, Any, Path]:
    """Run the SRFL direct pipeline through the host application's persistence hooks."""

    from tesis_domain_extensions.domains.single_row_facility_layout.analysis import (
        decision_case_id,
    )

    adapter = loaded.adapter
    config = loaded.record.domain_config
    if manifest.status != "running":
        manifest = application._update_group_manifest(
            adapter, manifest, status="running", new_active_segment=True
        )
        application.store.write_domain_run(manifest)
    started = monotonic()
    run_directory = application.store.results_root / manifest.domain_run_id
    total = adapter.theoretical_combinations(config)
    application._notify_grouped_progress("generation_started", total)
    try:
        artifacts, counters, frontiers, base_counts, valid_by_design, invalid_by_design = (
            evaluate_fast_cases(
                config,
                loaded.record.projection_context,
                domain_experiment_id=manifest.domain_experiment_id,
                run_directory=run_directory,
                timeout_ms=config.execution.integer_limits.exact_timeout_ms,
                is_cancel_requested=application.is_cancel_requested,
                on_progress=lambda completed, expected: application._notify_grouped_progress(
                    "generation_progress", completed, expected, completed
                ),
            )
        )
        projection = adapter.build_projection_record(
            domain_experiment_id=manifest.domain_experiment_id,
            created_at=manifest.created_at,
            config=config,
            context=loaded.record.projection_context,
            instance_nonce=loaded.record.instance_nonce,
        )
        generation = adapter.build_generation_metrics(
            config,
            CaseGenerationStatistics(
                theoretical_combinations=counters["theoretical_combinations"],
                valid_selections=counters["valid_selections"],
                invalid_combinations=counters["invalid_combinations"],
                forbidden_combinations=counters["forbidden_combinations"],
                cycle_pruned_branches=counters["cycle_pruned_branches"],
                degree_pruned_branches=counters["degree_pruned_branches"],
            ),
            duplicate_cases=0,
            core_cases=0,
        )
        designs = []
        for design_index, design in enumerate(config.study.designs):
            design_theoretical = 1 << (
                len(config.study.components) - len(design.base_component_ids)
            )
            frontier_path = (
                f"frontier/design-{design_index}.u64" if design.id in frontiers else None
            )
            order_indexes = {
                "case": f"orders/design-{design_index}-case.u64",
                "components": f"orders/design-{design_index}-components.u64",
                **{
                    f"criterion:{snapshot.definition.id}": (
                        f"orders/design-{design_index}-criterion-{snapshot.definition.id}.u64"
                    )
                    for snapshot in projection.objective_snapshots
                },
            }
            designs.append(
                FastDesignSummaryV21(
                    design_id=design.id,
                    design_title=design.title,
                    theoretical_combinations=large_non_negative_integer(design_theoretical),
                    valid_case_count=large_non_negative_integer(valid_by_design[design.id]),
                    invalid_combination_count=large_non_negative_integer(
                        invalid_by_design[design.id]
                    ),
                    base_case_id=decision_case_id(manifest.domain_experiment_id, design.id, []),
                    base_layout_count=(
                        large_non_negative_integer(base_counts[design.id])
                        if design.id in base_counts
                        else None
                    ),
                    pareto_case_count=large_non_negative_integer(len(frontiers.get(design.id, []))),
                    frontier_index=frontier_path,
                    order_indexes=order_indexes,
                )
            )
        summary = FastResultSummaryV21(
            schema_version="2.1.0",
            domain=config.domain,
            study_id=config.study.id,
            study_title=config.study.title,
            study_description=config.study.description,
            stations=config.study.stations,
            execution={
                "domain_run_id": manifest.domain_run_id,
                "domain_experiment_id": manifest.domain_experiment_id,
                "status": "completed",
                "mode": "high_performance",
                "counting_producer": COUNTING_PRODUCER.model_dump(mode="json"),
            },
            generation=generation,
            objective_snapshots=projection.objective_snapshots,
            designs=designs,
            limitations=[],
            files=artifacts,
        )
        _, report_path = application.store.write_result(manifest.domain_run_id, adapter, summary)
        duration = int((monotonic() - started) * 1000)
        completed_manifest = manifest.model_copy(
            update={
                "status": "completed",
                "generation": generation,
                "fast_counters": counters,
                "fast_artifacts": artifacts,
                "active_duration_ms": int(manifest.active_duration_ms) + duration,
                "active_started_at": None,
                "updated_at": application.store.clock(),
            }
        )
        application.store.write_domain_run(completed_manifest)
        return summary, completed_manifest, report_path
    except Exception as exc:
        cancelled = application.is_cancel_requested() or isinstance(
            exc, (DomainRunCancelled, FastWorkerCancelled, InterruptedError)
        )
        terminal_manifest = manifest.model_copy(
            update={
                "status": "cancelled" if cancelled else "failed",
                "fast_counters": {},
                "fast_artifacts": {},
                "active_duration_ms": int(manifest.active_duration_ms)
                + int((monotonic() - started) * 1000),
                "active_started_at": None,
                "updated_at": application.store.clock(),
            }
        )
        application.store.write_domain_run(terminal_manifest)
        if cancelled:
            raise DomainRunCancelled(terminal_manifest) from exc
        raise DomainExtensionError(
            "La ejecución de alto rendimiento falló; no hay resultado confirmado."
        ) from exc
