"""Read-only, exact analysis of confirmed SRFL results."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from fractions import Fraction
from itertools import combinations
from typing import Any

from tesis_domain_extensions.contracts.common import large_non_negative_integer

METRIC_IDS = (
    "base-flexibility",
    "criterion-extremes",
    "pareto-presence",
    "component-cooccurrence",
    "structural-overlap",
    "criterion-contributions",
    "frontier-warnings",
    "criterion-discrimination",
    "base-changes",
    "shared-design-patterns",
    "nearest-alternative",
    "criterion-conflicts",
    "pareto-sensitivity",
)
PAGE_SIZE = 50
EDGE_SEPARATOR = "\u2013"
MAX_INLINE_IDS = 50


def _normalize_counts(value: Any) -> Any:
    if type(value) is int:
        return large_non_negative_integer(value) if value >= 0 else value
    if isinstance(value, list):
        return [_normalize_counts(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_counts(item) for key, item in value.items()}
    return value


def _value(item: Any, key: str, default: Any = None) -> Any:
    return item.get(key, default) if isinstance(item, Mapping) else getattr(item, key, default)


def _exact(value: Any) -> Fraction | None:
    numerator = _value(value, "numerator")
    denominator = _value(value, "denominator")
    if isinstance(numerator, str) and numerator.lstrip("-").isdigit():
        numerator = int(numerator)
    if isinstance(denominator, str) and denominator.isdigit():
        denominator = int(denominator)
    if type(numerator) is int and type(denominator) is int and denominator > 0:
        return Fraction(numerator, denominator)
    return None


def _non_negative_count(value: Any) -> int | None:
    value = _value(value, "value", value)
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _flexibility_focus(counts: list[int], base_count: int) -> dict[str, Any] | None:
    """Summarize a dense low-flexibility cluster without losing high outliers."""
    if len(counts) < 3:
        return None
    ordered = sorted(counts)
    ninetieth = ordered[((len(ordered) - 1) * 9) // 10]
    if ninetieth * 4 >= base_count:
        return None
    upper_percent = next(
        bound for bound in (1, 2, 5, 10, 20, 25) if ninetieth * 100 <= base_count * bound
    )
    buckets = [0, 0, 0, 0, 0]
    above = 0
    for count in counts:
        if count * 100 > base_count * upper_percent:
            above += 1
        else:
            index = min(4, (count * 500) // (base_count * upper_percent))
            buckets[index] += 1
    return {
        "upper_percent": upper_percent,
        "counts": buckets,
        "within_cases": len(counts) - above,
        "above_cases": above,
    }


def _frontier(cases: list[Any]) -> list[Any]:
    return [
        case
        for case in cases
        if _value(_value(case, "pareto_classification", {}), "pareto_optimal") is True
        or _value(case, "pareto_optimal") is True
    ]


def _frontier_is_conclusive(cases: list[Any], frontier: list[Any]) -> bool:
    if not frontier:
        return False
    for case in cases:
        if _value(case, "scientific_status") == "inconclusive":
            return False
        if _value(case, "feasibility") == "inconclusive":
            return False
        if isinstance(case, Mapping) and "pareto_optimal" in case:
            if case["pareto_optimal"] is None:
                return False
        elif _value(_value(case, "pareto_classification", {}), "status") != "conclusive":
            return False
    return True


def _criterion(case: Any, objective_id: str) -> Fraction | None:
    vector = _value(case, "criteria_vector", {})
    if isinstance(vector, Mapping) and objective_id in vector:
        return _exact(vector[objective_id])
    retained = _value(case, "retained_layouts")
    if _value(retained, "objective_id") == objective_id:
        fraction = _value(retained, "fraction")
        return _exact(fraction)
    for item in [
        *_value(case, "rel_closeness", []),
        *([_value(case, "captured_flow")] if _value(case, "captured_flow") is not None else []),
        *_value(case, "adjacency_values", []),
    ]:
        if _value(item, "objective_id") != objective_id or _value(item, "status") != "conclusive":
            continue
        if _value(item, "total") is not None:
            return Fraction(str(_value(item, "total")))
        return _exact(_value(item, "fraction"))
    return None


def _criterion_comparisons(
    selected: Any, alternative: Any, objectives: list[Any]
) -> dict[str, Any]:
    comparisons = {}
    for objective in objectives:
        objective_id = _value(_value(objective, "definition", objective), "id")
        selected_value = _criterion(selected, objective_id)
        alternative_value = _criterion(alternative, objective_id)
        change = (
            alternative_value - selected_value
            if alternative_value is not None and selected_value is not None
            else None
        )
        comparisons[objective_id] = {
            "selected": str(selected_value) if selected_value is not None else None,
            "alternative": str(alternative_value) if alternative_value is not None else None,
            "change": str(change) if change is not None else None,
        }
    return comparisons


def _dominates_without_ties(
    other: Any,
    candidate_values: Mapping[str, Fraction | None],
    dimensions: list[str],
    directions: Mapping[str, str],
) -> bool:
    strictly_better = False
    for key in dimensions:
        left = _criterion(other, key)
        right = candidate_values[key]
        if left is None or right is None:
            return False
        at_least_as_good = left >= right if directions[key] == "maximize" else left <= right
        if not at_least_as_good:
            return False
        strictly_better = strictly_better or left != right
    return strictly_better


def analyze_metric(  # noqa: C901 - metric-specific aggregation is kept in one pure dispatcher
    *,
    metric_id: str,
    design_id: str | None,
    criterion_id: str | None,
    case_id: str | None,
    cursor: int,
    designs: list[Any],
    objectives: list[Any],
    base_layout_count: Any = None,
    include_all_rows: bool = False,
) -> dict[str, Any]:
    """Build one bounded page and compact summary from validated case rows."""
    if metric_id not in METRIC_IDS:
        raise ValueError("identificador de métrica desconocido")
    if cursor < 0:
        raise ValueError("cursor inválido")
    selected = [d for d in designs if design_id is None or _value(d, "design_id") == design_id]
    if design_id is not None and not selected:
        raise ValueError("el diseño no pertenece al resultado confirmado")
    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    if metric_id == "shared-design-patterns":
        appearances: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in selected:
            all_cases = list(_value(item, "cases", []))
            frontier = _frontier(all_cases)
            base_case = next(
                (case for case in all_cases if not _value(case, "added_component_ids", [])),
                None,
            )
            base_edges = (
                set(map(tuple, _value(base_case, "edges", []))) if base_case is not None else set()
            )
            optional_edges = {
                tuple(sorted(edge)) for case in all_cases for edge in _value(case, "edges", [])
            } - base_edges
            present_edges = {
                tuple(sorted(edge)) for case in frontier for edge in _value(case, "edges", [])
            }
            for edge in base_edges | optional_edges:
                state = (
                    "obligatoria"
                    if edge in base_edges
                    else "presente en frontera"
                    if edge in present_edges
                    else "opcional y ausente"
                )
                appearances[edge].append(
                    {
                        "design_id": _value(item, "design_id"),
                        "state": state,
                        "optional_denominator": edge in optional_edges,
                        "frontier_status": "conclusive" if frontier else "inconclusive",
                    }
                )
        rows = [
            {"adjacency": EDGE_SEPARATOR.join(edge), "designs": values}
            for edge, values in appearances.items()
        ]
        summary = {"designs": len(selected), "comparison": "structural patterns only"}
    for design in selected if metric_id != "shared-design-patterns" else []:
        cases = list(_value(design, "cases", []))
        frontier = _frontier(cases)
        frontier_conclusive = _frontier_is_conclusive(cases, frontier)
        if metric_id == "base-flexibility":
            base = _value(design, "base_layout_count", base_layout_count)
            base_count = _non_negative_count(base)
            distribution = [0, 0, 0, 0]
            compatible_counts: list[int] = []
            for case in frontier:
                retained = _value(case, "retained_layouts", {})
                count = _non_negative_count(_value(case, "compatible_layout_count"))
                if count is None and _value(retained, "status") == "conclusive":
                    count = _non_negative_count(_value(retained, "compatible_layout_count"))
                if (
                    base_count is not None
                    and base_count > 0
                    and count is not None
                    and count <= base_count
                ):
                    ratio = Fraction(count, base_count)
                    bucket = min(3, (count * 4) // base_count)
                    distribution[bucket] += 1
                    compatible_counts.append(count)
                    rows.append(
                        {
                            "case_id": _value(case, "case_id"),
                            "numerator": ratio.numerator,
                            "denominator": ratio.denominator,
                            "percent": str(ratio * 100),
                        }
                    )
            summary = {
                "status": (
                    "conclusive"
                    if frontier_conclusive and len(rows) == len(frontier)
                    else "inconclusive"
                ),
                "denominator": str(len(frontier)),
                "base_layout_count": base_count,
                "analyzed_cases": len(rows),
                "missing_cases": len(frontier) - len(rows),
                "distribution": [
                    {"from_percent": lower, "to_percent": lower + 25, "count": amount}
                    for lower, amount in zip((0, 25, 50, 75), distribution, strict=True)
                ],
                "focus_distribution": (
                    _flexibility_focus(compatible_counts, base_count)
                    if base_count is not None and base_count > 0
                    else None
                ),
            }
        elif metric_id in {"criterion-extremes", "criterion-discrimination"}:
            for objective in objectives:
                definition = _value(objective, "definition", objective)
                oid = _value(definition, "id")
                if criterion_id is not None and oid != criterion_id:
                    continue
                values: dict[Fraction, list[str]] = defaultdict(list)
                for case in frontier:
                    value = _criterion(case, oid)
                    if value is not None:
                        values[value].append(str(_value(case, "case_id")))
                if not values:
                    rows.append(
                        {
                            "criterion_id": oid,
                            "name": _value(definition, "name"),
                            "status": "inconclusive",
                            "unit": _value(definition, "unit"),
                        }
                    )
                    continue
                direction = _value(definition, "direction")
                ordered = sorted(values)
                if metric_id == "criterion-extremes":
                    best = ordered[-1] if direction == "maximize" else ordered[0]
                    worst = ordered[0] if direction == "maximize" else ordered[-1]
                    rows.append(
                        {
                            "criterion_id": oid,
                            "name": _value(definition, "name"),
                            "unit": _value(definition, "unit"),
                            "best": str(best),
                            "best_case_ids": values[best][:MAX_INLINE_IDS],
                            "best_case_count": len(values[best]),
                            "worst": str(worst),
                            "worst_case_ids": values[worst][:MAX_INLINE_IDS],
                            "worst_case_count": len(values[worst]),
                        }
                    )
                else:
                    rows.extend(
                        {
                            "criterion_id": oid,
                            "name": _value(definition, "name"),
                            "unit": _value(definition, "unit"),
                            "value": str(value),
                            "count": len(ids),
                            "case_ids": ids[:MAX_INLINE_IDS],
                            "case_count": len(ids),
                        }
                        for value, ids in sorted(values.items())
                    )
            summary = {
                "frontier_cases": str(len(frontier)),
                "denominator": str(len(frontier)),
                "status": "conclusive" if frontier_conclusive else "inconclusive",
            }
        elif metric_id in {
            "pareto-presence",
            "component-cooccurrence",
            "structural-overlap",
            "frontier-warnings",
            "base-changes",
            "criterion-contributions",
        }:
            if metric_id == "pareto-presence":
                base_case = next(
                    (case for case in cases if not _value(case, "added_component_ids", [])), None
                )
                base_edges = (
                    set(map(tuple, _value(base_case, "edges", [])))
                    if base_case is not None
                    else set()
                )
                edge_forests: dict[tuple[str, str], set[str]] = defaultdict(set)
                component_selections: Counter[str] = Counter()
                for case in frontier:
                    forest = str(_value(case, "forest_id"))
                    for edge in _value(case, "edges", []):
                        canonical = tuple(sorted(edge))
                        if canonical not in base_edges:
                            edge_forests[canonical].add(forest)
                    component_selections.update(_value(case, "added_component_ids", []))
                rows = [
                    {
                        "kind": "adjacency",
                        "id": EDGE_SEPARATOR.join(edge),
                        "count": len(forests),
                        "denominator": len({str(_value(c, "forest_id")) for c in frontier}),
                    }
                    for edge, forests in edge_forests.items()
                ]
                rows += [
                    {"kind": "component", "id": key, "count": count, "denominator": len(frontier)}
                    for key, count in component_selections.items()
                ]
                rows.sort(
                    key=lambda row: (
                        0 if row["kind"] == "adjacency" else 1,
                        -row["count"],
                        row["id"],
                    )
                )
                summary = {
                    "physical_frontier_forests": str(
                        len({str(_value(c, "forest_id")) for c in frontier})
                    ),
                    "frontier_selections": str(len(frontier)),
                    "status": "conclusive" if frontier_conclusive else "inconclusive",
                }
            elif metric_id == "component-cooccurrence":
                occurrences: Counter[str] = Counter()
                pairs: Counter[tuple[str, str]] = Counter()
                for case in frontier:
                    components = sorted(set(_value(case, "added_component_ids", [])))
                    occurrences.update(components)
                    pairs.update(combinations(components, 2))
                rows = [
                    {
                        "components": list(pair),
                        "together": count,
                        "first_alone": occurrences[pair[0]],
                        "second_alone": occurrences[pair[1]],
                        "denominator": len(frontier),
                    }
                    for pair, count in sorted(pairs.items(), key=lambda item: (-item[1], item[0]))
                ]
                summary = {
                    "frontier_selections": str(len(frontier)),
                    "status": "conclusive" if frontier_conclusive else "inconclusive",
                }
            elif metric_id == "structural-overlap":
                groups: dict[str, list[str]] = defaultdict(list)
                cases_by_id = {}
                for case in frontier:
                    forest = str(_value(case, "forest_id"))
                    cid = str(_value(case, "case_id"))
                    groups[forest].append(cid)
                    cases_by_id[cid] = case
                rows = [
                    {
                        "forest_id": forest,
                        "count": len(ids),
                        "case_ids": ids[:MAX_INLINE_IDS],
                        "case_count": len(ids),
                        "components": sorted(
                            set().union(
                                *[set(_value(cases_by_id[cid], "component_ids", [])) for cid in ids]
                            )
                        ),
                    }
                    for forest, ids in groups.items()
                    if len(ids) > 1
                ]
                summary = {
                    "frontier_selections": str(len(frontier)),
                    "physical_forests": str(len(groups)),
                    "status": "conclusive" if frontier_conclusive else "inconclusive",
                }
            elif metric_id == "frontier-warnings":
                rows = [
                    {
                        "case_id": _value(case, "case_id"),
                        "adjacency": EDGE_SEPARATOR.join(
                            [_value(f, "first_station_id", ""), _value(f, "second_station_id", "")]
                        ),
                        "cause": _value(f, "cause"),
                        "explanation": _value(f, "explanation"),
                    }
                    for case in frontier
                    for f in _value(case, "findings", [])
                    if _value(f, "policy") == "warn"
                ]
                summary = {
                    "warnings": str(len(rows)),
                    "frontier_selections": str(len(frontier)),
                    "status": "conclusive" if frontier_conclusive else "inconclusive",
                }
            elif metric_id == "base-changes":
                base_case = next(
                    (case for case in cases if not _value(case, "added_component_ids", [])), None
                )
                if base_case is None:
                    summary = {
                        "status": "not_applicable",
                        "message": "Este diseño de control tiene base vacía.",
                    }
                    continue
                base_edges = set(map(tuple, _value(base_case, "edges", [])))
                for case in frontier:
                    new_edges = sorted(set(map(tuple, _value(case, "edges", []))) - base_edges)
                    rows.append(
                        {
                            "case_id": _value(case, "case_id"),
                            "new_adjacencies": len(new_edges),
                            "edges": new_edges,
                        }
                    )
                summary = {
                    "frontier_selections": str(len(frontier)),
                    "status": "conclusive" if frontier_conclusive else "inconclusive",
                }
            else:
                for case in frontier:
                    flow = _value(case, "captured_flow")
                    objective_values = list(_value(case, "adjacency_values", []))
                    if flow is not None:
                        objective_values.append(flow)
                    for objective in objective_values:
                        oid = _value(objective, "objective_id")
                        if criterion_id is not None and oid != criterion_id:
                            continue
                        for contribution in _value(objective, "contributions", []):
                            rows.append(
                                {
                                    "case_id": _value(case, "case_id"),
                                    "criterion_id": oid,
                                    "unit": _value(objective, "unit"),
                                    "period": _value(
                                        objective,
                                        "reference_period",
                                        _value(objective, "horizon"),
                                    ),
                                    "direction": _value(objective, "direction"),
                                    "adjacency": EDGE_SEPARATOR.join(
                                        [
                                            str(_value(contribution, "first_station_id")),
                                            str(_value(contribution, "second_station_id")),
                                        ]
                                    ),
                                    "contribution": str(_value(contribution, "total")),
                                }
                            )
                summary = {
                    "frontier_selections": str(len(frontier)),
                    "status": "conclusive" if frontier_conclusive else "inconclusive",
                }
        elif metric_id == "nearest-alternative":
            selected_case = next(
                (case for case in cases if _value(case, "case_id") == case_id), None
            )
            if selected_case is None:
                summary = {
                    "status": "not_applicable",
                    "message": "Elegí un caso para buscar su alternativa más cercana.",
                }
            else:
                edges = set(map(tuple, _value(selected_case, "edges", [])))
                candidates = [
                    case
                    for case in frontier
                    if _value(case, "forest_id") != _value(selected_case, "forest_id")
                ]
                distances = [
                    (
                        len(edges.symmetric_difference(set(map(tuple, _value(case, "edges", []))))),
                        case,
                    )
                    for case in candidates
                ]
                if distances:
                    nearest = min(distance for distance, _ in distances)
                    rows = [
                        {
                            "case_id": _value(case, "case_id"),
                            "distance": nearest,
                            "removed": sorted(edges - set(map(tuple, _value(case, "edges", [])))),
                            "added": sorted(set(map(tuple, _value(case, "edges", []))) - edges),
                            "criteria": _criterion_comparisons(selected_case, case, objectives),
                        }
                        for distance, case in distances
                        if distance == nearest
                    ]
                    summary = {
                        "selected_case_id": case_id,
                        "minimum_distance": nearest,
                        "ties": len(rows),
                    }
                else:
                    summary = {
                        "status": "not_applicable",
                        "message": (
                            "Las alternativas comparten el mismo bosque; consultá "
                            "Superposición estructural."
                        ),
                    }
        elif metric_id in {"criterion-conflicts", "pareto-sensitivity"}:
            directions = {
                _value(_value(item, "definition", item), "id"): _value(
                    _value(item, "definition", item), "direction"
                )
                for item in objectives
            }
            if metric_id == "pareto-sensitivity" and criterion_id is None:
                summary = {
                    "status": "not_applicable",
                    "message": "Elegí un criterio para iniciar el recálculo.",
                }
            elif metric_id == "pareto-sensitivity" and len(directions) <= 1:
                summary = {
                    "status": "not_applicable",
                    "message": "No aplica con un solo criterio activo.",
                }
            elif metric_id == "pareto-sensitivity":
                remaining = [key for key in directions if key != criterion_id]
                valid = [
                    case
                    for case in cases
                    if all(_criterion(case, key) is not None for key in remaining)
                ]
                changed_frontier = []
                for candidate in valid:
                    candidate_values = {key: _criterion(candidate, key) for key in remaining}
                    dominated = any(
                        other is not candidate
                        and _dominates_without_ties(other, candidate_values, remaining, directions)
                        for other in valid
                    )
                    if not dominated:
                        changed_frontier.append(candidate)
                old_ids = {str(_value(case, "case_id")) for case in frontier}
                new_ids = {str(_value(case, "case_id")) for case in changed_frontier}
                cases_by_id = {str(_value(case, "case_id")): case for case in cases}
                rows = [
                    {
                        "case_id": cid,
                        "added_component_ids": list(
                            _value(cases_by_id[cid], "added_component_ids", [])
                        ),
                        "status": "remains" if cid in old_ids else "enters",
                    }
                    for cid in sorted(new_ids)
                ] + [
                    {
                        "case_id": cid,
                        "added_component_ids": list(
                            _value(cases_by_id[cid], "added_component_ids", [])
                        ),
                        "status": "leaves",
                    }
                    for cid in sorted(old_ids - new_ids)
                ]
                summary = {
                    "excluded_criterion_id": criterion_id,
                    "dimensions": remaining,
                    "valid_cases": len(valid),
                    "official_frontier": len(old_ids),
                    "alternative_frontier": len(new_ids),
                    "status": "conclusive",
                }
            else:
                ties_excluded = 0
                incomplete_excluded = 0
                pair_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
                for left, right in combinations(frontier, 2):
                    for first, second in combinations(directions, 2):
                        a1, a2, b1, b2 = (
                            _criterion(left, first),
                            _criterion(right, first),
                            _criterion(left, second),
                            _criterion(right, second),
                        )
                        if a1 is None or a2 is None or b1 is None or b2 is None:
                            incomplete_excluded += 1
                            continue
                        if a1 == a2 or b1 == b2:
                            ties_excluded += 1
                            pair_counts[(first, second)]["ties_excluded"] += 1
                            continue
                        win1 = (a1 > a2) if directions[first] == "maximize" else (a1 < a2)
                        win2 = (b1 > b2) if directions[second] == "maximize" else (b1 < b2)
                        outcome = "joint-improvement" if win1 == win2 else "conflict"
                        pair_counts[(first, second)][outcome] += 1
                        rows.append(
                            {
                                "criteria": [first, second],
                                "cases": [
                                    str(_value(left, "case_id")),
                                    str(_value(right, "case_id")),
                                ],
                                "outcome": outcome,
                                "values": {first: [str(a1), str(a2)], second: [str(b1), str(b2)]},
                            }
                        )
                conflicts = sum(row["outcome"] == "conflict" for row in rows)
                summary = {
                    "comparisons_without_ties": len(rows),
                    "conflicts": conflicts,
                    "joint_improvements": len(rows) - conflicts,
                    "ties_excluded": ties_excluded,
                    "incomplete_excluded": incomplete_excluded,
                    "by_criterion_pair": [
                        {
                            "criteria": list(pair),
                            **dict(counts),
                            "denominator": counts["conflict"] + counts["joint-improvement"],
                        }
                        for pair, counts in pair_counts.items()
                    ],
                    "criteria_count": len(directions),
                    "expected_two_criterion_frontier_tradeoff": len(directions) == 2,
                    "status": "conclusive" if frontier_conclusive else "inconclusive",
                }
    if metric_id == "base-flexibility":
        rows.sort(
            key=lambda row: (
                -Fraction(int(row["numerator"]), int(row["denominator"])),
                str(row["case_id"]),
            )
        )
    total = len(rows)
    page = rows[cursor : cursor + PAGE_SIZE]
    response = {
        "metric_id": metric_id,
        "design_id": design_id,
        "summary": _normalize_counts(summary),
        "status": summary.get("status", "conclusive" if rows else "inconclusive"),
        "total": large_non_negative_integer(total),
        "rows": _normalize_counts(page),
        "next_cursor": cursor + PAGE_SIZE if cursor + PAGE_SIZE < total else None,
    }
    if include_all_rows:
        response["all_rows"] = rows
    return response
