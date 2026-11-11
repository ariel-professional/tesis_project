"""Bounded-memory, exact-input projection for confirmed fast SRFL results."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import floor, log1p, sqrt
from typing import Any, Literal

from tesis_domain_extensions.errors import DomainExtensionError

ScaleMode = Literal["automatic", "linear", "square-root", "adjusted-log", "percentile"]
Section = Literal["groups", "frontier_positions"]
LEVEL_SIZES = ((16, 8), (32, 16), (64, 32))
SCALE_MODES: tuple[Literal["linear", "square-root", "adjusted-log", "percentile"], ...] = (
    "linear",
    "square-root",
    "adjusted-log",
    "percentile",
)


@dataclass(frozen=True)
class ProjectionRequest:
    design_id: str
    x_objective_id: str
    y_objective_id: str
    x_scale: ScaleMode
    y_scale: ScaleMode
    x_log_k: float
    y_log_k: float

    @property
    def cache_key(self) -> tuple[object, ...]:
        return (
            self.design_id,
            self.x_objective_id,
            self.y_objective_id,
            self.x_scale,
            self.y_scale,
            self.x_log_k,
            self.y_log_k,
        )


@dataclass
class Cell:
    count: int
    sum_x: float
    sum_y: float
    min_x: Fraction
    max_x: Fraction
    min_y: Fraction
    max_y: Fraction
    case_id: str | None

    def merge(self, other: Cell) -> None:
        self.count += other.count
        self.sum_x += other.sum_x
        self.sum_y += other.sum_y
        self.min_x = min(self.min_x, other.min_x)
        self.max_x = max(self.max_x, other.max_x)
        self.min_y = min(self.min_y, other.min_y)
        self.max_y = max(self.max_y, other.max_y)
        self.case_id = None

    def as_json(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "count": self.count,
            "x": self.sum_x / self.count,
            "y": self.sum_y / self.count,
            "x_min": _fraction_json(self.min_x),
            "x_max": _fraction_json(self.max_x),
            "y_min": _fraction_json(self.min_y),
            "y_max": _fraction_json(self.max_y),
        }
        if self.count == 1 and self.case_id is not None:
            result["case_id"] = self.case_id
        return result


@dataclass(frozen=True)
class AxisProjection:
    objective_id: str
    mode: str
    minimum: Fraction
    maximum: Fraction
    k: float
    unique_values: tuple[Fraction, ...]
    positions: dict[Fraction, float]

    def position(self, value: Fraction) -> float:
        return self.positions[value]

    def json(self) -> dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "scale": self.mode,
            "minimum": _fraction_json(self.minimum),
            "maximum": _fraction_json(self.maximum),
            "ticks": [
                {"position": step / 5, "label": _format_tick(self._tick_value(step / 5))}
                for step in range(6)
            ],
        }

    def _tick_value(self, position: float) -> float:
        if self.minimum == self.maximum:
            return float(self.minimum)
        if self.mode == "percentile":
            rank = position * max(1, len(self.unique_values) - 1)
            low = int(rank)
            high = min(len(self.unique_values) - 1, low + 1)
            ratio = rank - low
            return (
                float(self.unique_values[low])
                + (float(self.unique_values[high]) - float(self.unique_values[low])) * ratio
            )
        if self.mode == "square-root":
            position *= position
        elif self.mode == "adjusted-log":
            position = (pow(1 + self.k, position) - 1) / self.k
        return float(self.minimum) + position * (float(self.maximum) - float(self.minimum))


@dataclass(frozen=True)
class PlotProjection:
    axes: dict[str, Any]
    considered_count: int
    frontier_positions: tuple[dict[str, Any], ...]
    levels: tuple[tuple[dict[str, Any], ...], ...]
    dominated_count: int

    def page(self, *, section: Section, level: int, cursor: int) -> dict[str, Any]:
        if level not in {0, 1, 2} or cursor < 0:
            raise DomainExtensionError("El nivel o cursor de proyección no es válido.")
        items = self.frontier_positions if section == "frontier_positions" else self.levels[level]
        selected = items[cursor : cursor + 50]
        next_cursor = cursor + 50 if cursor + 50 < len(items) else None
        return {
            "axes": self.axes,
            "considered_count": self.considered_count,
            "dominated_count": self.dominated_count,
            "level": level,
            "section": section,
            "grid": {"columns": LEVEL_SIZES[level][0], "rows": LEVEL_SIZES[level][1]},
            "total": len(items),
            "items": list(selected),
            "next_cursor": next_cursor,
        }


def build_projection(  # noqa: C901 - one confirmed scan builds the complete cached projection
    reader: Any,
    design: Any,
    request: ProjectionRequest,
) -> PlotProjection:
    """Scan one confirmed design and retain only bounded cells plus frontier marks."""

    if request.x_objective_id == "" or request.y_objective_id == "":
        raise DomainExtensionError("El gráfico requiere objetivos para ambos ejes.")
    if design.frontier_index is None:
        frontier_ids: set[str] = set()
    else:
        frontier_ids = set()
        count = reader.index_count(design.frontier_index)
        for page in range((count + 49) // 50):
            frontier_ids.update(
                str(case["case_id"]) for case in reader.page(design.frontier_index, page)
            )

    cases: list[tuple[str, Fraction, Fraction]] = []
    order = design.order_indexes.get("case")
    if order is None:
        raise DomainExtensionError("El orden de casos no está disponible para proyectar.")
    total = reader.index_count(order)
    for page in range((total + 49) // 50):
        for case in reader.page(order, page):
            if case.get("design_id") != request.design_id:
                continue
            vector = case.get("criteria_vector", {})
            x_value = _case_value(vector, request.x_objective_id)
            y_value = _case_value(vector, request.y_objective_id)
            if x_value is None or y_value is None:
                continue
            cases.append((str(case["case_id"]), x_value, y_value))
    if not cases:
        raise DomainExtensionError("No hay casos con valores para los ejes seleccionados.")

    values_x = [item[1] for item in cases]
    values_y = [item[2] for item in cases]
    mode_x, mode_y = _choose_modes(
        values_x,
        values_y,
        request.x_scale,
        request.y_scale,
        request.x_log_k,
        request.y_log_k,
    )
    axis_x = _axis(request.x_objective_id, values_x, mode_x, request.x_log_k)
    axis_y = _axis(request.y_objective_id, values_y, mode_y, request.y_log_k)
    fine: dict[tuple[int, int], Cell] = {}
    frontier_positions: list[dict[str, Any]] = []
    considered = 0
    dominated = 0
    for case_id, x_value, y_value in cases:
        x, y = axis_x.position(x_value), axis_y.position(y_value)
        considered += 1
        if design.frontier_index is None:
            continue
        if case_id in frontier_ids:
            frontier_positions.append({"case_id": case_id, "x": x, "y": y})
            continue
        dominated += 1
        key = (min(63, floor(x * 64)), min(31, floor(y * 32)))
        point = Cell(1, x, y, x_value, x_value, y_value, y_value, case_id)
        existing = fine.get(key)
        if existing is None:
            fine[key] = point
        else:
            existing.merge(point)
    frontier_positions.sort(key=lambda point: point["case_id"])
    levels = tuple(
        tuple(_cell_json(cell) for cell in _coarsen(fine, divisor).values())
        for divisor in (4, 2, 1)
    )
    return PlotProjection(
        axes={"x": axis_x.json(), "y": axis_y.json()},
        considered_count=considered,
        frontier_positions=tuple(frontier_positions),
        levels=levels,
        dominated_count=dominated,
    )


def _coarsen(fine: dict[tuple[int, int], Cell], divisor: int) -> dict[tuple[int, int], Cell]:
    cells: dict[tuple[int, int], Cell] = {}
    for (x, y), source in fine.items():
        key = (x // divisor, y // divisor)
        target = cells.get(key)
        if target is None:
            cells[key] = Cell(
                source.count,
                source.sum_x,
                source.sum_y,
                source.min_x,
                source.max_x,
                source.min_y,
                source.max_y,
                source.case_id if source.count == 1 else None,
            )
        else:
            target.merge(source)
    return cells


def _cell_json(cell: Cell) -> dict[str, Any]:
    return cell.as_json()


def _case_value(vector: Any, objective_id: str) -> Fraction | None:
    if not isinstance(vector, dict):
        return None
    value = vector.get(objective_id)
    if not isinstance(value, dict):
        return None
    try:
        return Fraction(int(value["numerator"]), int(value["denominator"]))
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def _axis(objective_id: str, values: list[Fraction], mode: str, k: float) -> AxisProjection:
    unique = tuple(sorted(set(values)))
    minimum, maximum = unique[0], unique[-1]
    ranks = _ranks(unique)
    positions = {
        value: _scaled_position(_base_position(value, minimum, maximum), mode, k, ranks[value])
        for value in unique
    }
    return AxisProjection(
        objective_id=objective_id,
        mode=mode,
        minimum=minimum,
        maximum=maximum,
        k=k,
        unique_values=unique,
        positions=positions,
    )


def _ranks(values: tuple[Fraction, ...]) -> dict[Fraction, float]:
    divisor = max(1, len(values) - 1)
    return {value: index / divisor for index, value in enumerate(values)}


def _base_position(value: Fraction, minimum: Fraction, maximum: Fraction) -> float:
    if minimum == maximum:
        return 0.5
    return min(1.0, max(0.0, float((value - minimum) / (maximum - minimum))))


def _scaled_position(base: float, mode: str, k: float, rank: float) -> float:
    if mode == "square-root":
        return sqrt(base)
    if mode == "adjusted-log":
        return log1p(k * base) / log1p(k)
    if mode == "percentile":
        return rank
    return base


def _choose_modes(
    x_values: list[Fraction],
    y_values: list[Fraction],
    x_mode: ScaleMode,
    y_mode: ScaleMode,
    x_k: float,
    y_k: float,
) -> tuple[str, str]:
    x_candidates = SCALE_MODES if x_mode == "automatic" else (x_mode,)
    y_candidates = SCALE_MODES if y_mode == "automatic" else (y_mode,)
    best = (x_candidates[0], y_candidates[0])
    best_score: int | None = None
    minimum_x, maximum_x = min(x_values), max(x_values)
    minimum_y, maximum_y = min(y_values), max(y_values)
    unique_x = tuple(sorted(set(x_values)))
    unique_y = tuple(sorted(set(y_values)))
    ranks_x = _ranks(unique_x)
    ranks_y = _ranks(unique_y)
    x_base = [_base_position(value, minimum_x, maximum_x) for value in x_values]
    y_base = [_base_position(value, minimum_y, maximum_y) for value in y_values]
    x_rank = [ranks_x[value] for value in x_values]
    y_rank = [ranks_y[value] for value in y_values]
    for mode_x in x_candidates:
        for mode_y in y_candidates:
            occupied: dict[tuple[int, int], int] = {}
            for xb, xr, yb, yr in zip(x_base, x_rank, y_base, y_rank, strict=True):
                x = min(63, floor(_scaled_position(xb, mode_x, x_k, xr) * 64))
                y = min(31, floor(_scaled_position(yb, mode_y, y_k, yr) * 32))
                key = (x, y)
                occupied[key] = occupied.get(key, 0) + 1
            score = sum(count * (count - 1) // 2 for count in occupied.values())
            if best_score is None or score < best_score:
                best_score = score
                best = (mode_x, mode_y)
    return best


def _fraction_json(value: Fraction) -> dict[str, str]:
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def _format_tick(value: float) -> str:
    return f"{value:.5g}"
