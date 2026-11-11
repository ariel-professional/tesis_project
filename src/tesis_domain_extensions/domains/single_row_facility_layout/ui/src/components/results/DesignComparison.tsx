import { ActionButton, ActionIconButton, ButtonVariant, IconButton, Modal, NumberField, SelectField } from "@domain-ui-kit";
import type { LayoutCaseResultV2 } from "@domain-ui-sdk";
import { useEffect, useMemo, useState } from "react";
import { formatFractionDecimal } from "./format-fraction";
import type {
  FrontierProjectionPoint,
  PlotProjectionGroup,
  PlotProjectionResult,
  SrflPlotPoint,
} from "../../model/srfl-result-source";

type Exact = { numerator: number | string; denominator: number | string };
type Scalar = { numerator: bigint; denominator: bigint };
type Dimension = { scalar: Scalar; label: string };
type Point = {
  item: LayoutCaseResultV2;
  values: Record<string, Dimension>;
  equivalents: readonly LayoutCaseResultV2[];
};
type ChartPoint = {
  caseId: string | null;
  status: string;
  values: Record<string, Dimension>;
  position?: { x: number; y: number };
  group?: PlotProjectionGroup;
};
type SortDirection = "ascending" | "descending";
type ScaleMode = "automatic" | ConcreteScaleMode;
type ConcreteScaleMode =
  | "linear"
  | "square-root"
  | "adjusted-log"
  | "percentile";
type VisualReductionLevel = "low" | "medium" | "high";
type AxisTransform = {
  mode: ConcreteScaleMode;
  minimum: Scalar;
  maximum: Scalar;
  levels: readonly Scalar[];
  percentilePositions: ReadonlyMap<string, number>;
  k: number;
};
type AxisContext = {
  modes: readonly [ConcreteScaleMode, ConcreteScaleMode];
  x: AxisTransform;
  y: AxisTransform;
};
type AdjacencyValueObservation = {
  objective_id: string;
  status: string;
  total?: number | string | null;
  unit: string;
  reference_period?: string | null;
};
const CASE_SORT = "case";
const COMPONENTS_SORT = "components";
const CLASSIFICATION_SORT = "classification";
const objectiveSort = (id: string) => `objective:${id}`;
const PLOT_LAYOUT = {
  compact: {
    width: 600,
    height: 390,
    left: 64,
    right: 570,
    top: 28,
    bottom: 320,
    dominatedRadius: 4,
  },
  expanded: {
    width: 1200,
    height: 720,
    left: 96,
    right: 1140,
    top: 48,
    bottom: 640,
    dominatedRadius: 5,
  },
} as const;
const REDUCTION_LEVEL_FACTOR: Readonly<Record<VisualReductionLevel, number>> = {
  low: 1,
  medium: 2,
  high: 4,
};

function fraction(value: Exact | null | undefined): Scalar | null {
  return value == null
    ? null
    : {
        numerator: BigInt(value.numerator),
        denominator: BigInt(value.denominator),
      };
}
function decimal(value: number | string | null | undefined): Scalar | null {
  if (value == null) return null;
  const match = String(value).match(/^([+-]?)(\d+)(?:\.(\d+))?$/);
  if (match === null) return null;
  const decimals = match[3] ?? "";
  return {
    numerator: (match[1] === "-" ? -1n : 1n) * BigInt(`${match[2]}${decimals}`),
    denominator: 10n ** BigInt(decimals.length),
  };
}
function compareScalar(left: Scalar, right: Scalar): number {
  const difference =
    left.numerator * right.denominator - right.numerator * left.denominator;
  return difference < 0n ? -1 : difference > 0n ? 1 : 0;
}
function scalarNumber(value: Scalar): number {
  return Number(value.numerator) / Number(value.denominator);
}
function formatTick(value: number): string {
  return Number.isFinite(value)
    ? value.toLocaleString("es-AR", { maximumSignificantDigits: 5 })
    : "—";
}
const ZERO: Scalar = { numerator: 0n, denominator: 1n };
const AUTOMATIC_CANDIDATES: readonly ConcreteScaleMode[] = [
  "linear",
  "square-root",
  "adjusted-log",
  "percentile",
];

function positiveNumber(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
function uniqueScalars(values: readonly Scalar[]): Scalar[] {
  const sorted = [...values].sort(compareScalar);
  return sorted.filter(
    (value, index) =>
      index === 0 || compareScalar(value, sorted[index - 1]!) !== 0,
  );
}
function scalarKey(value: Scalar): string {
  return `${value.numerator}/${value.denominator}`;
}
function axisTransform(
  values: readonly Scalar[],
  mode: ConcreteScaleMode,
  k: number,
): AxisTransform {
  const levels = uniqueScalars(values);
  const divisor = Math.max(1, levels.length - 1);
  return {
    mode,
    minimum: levels[0] ?? ZERO,
    maximum: levels.at(-1) ?? ZERO,
    levels,
    percentilePositions: new Map(
      levels.map((value, index) => [scalarKey(value), index / divisor]),
    ),
    k,
  };
}
function scaleRatio(value: Scalar, transform: AxisTransform): number {
  const range = subtract(transform.maximum, transform.minimum);
  const offset = subtract(value, transform.minimum);
  const ratio = range.numerator === 0n ? 0.5 : boundedRatio(offset, range);
  if (transform.mode === "square-root") return Math.sqrt(ratio);
  if (transform.mode === "adjusted-log")
    return Math.log1p(transform.k * ratio) / Math.log1p(transform.k);
  if (transform.mode === "percentile") {
    return transform.percentilePositions.get(scalarKey(value)) ?? 0;
  }
  return ratio;
}
function tickValue(ratio: number, transform: AxisTransform): number {
  if (transform.mode === "percentile") {
    const position = ratio * (transform.levels.length - 1);
    const lowerIndex = Math.floor(position);
    const upperIndex = Math.ceil(position);
    const lower = scalarNumber(transform.levels[lowerIndex] ?? ZERO);
    const upper = scalarNumber(
      transform.levels[upperIndex] ?? transform.maximum,
    );
    return lower + (upper - lower) * (position - lowerIndex);
  }
  const base =
    transform.mode === "square-root"
      ? ratio * ratio
      : transform.mode === "adjusted-log"
        ? Math.expm1(ratio * Math.log1p(transform.k)) / transform.k
        : ratio;
  const low = scalarNumber(transform.minimum);
  const high = scalarNumber(transform.maximum);
  return low + base * (high - low);
}

function subtract(left: Scalar, right: Scalar): Scalar {
  return {
    numerator:
      left.numerator * right.denominator - right.numerator * left.denominator,
    denominator: left.denominator * right.denominator,
  };
}
function boundedRatio(numerator: Scalar, denominator: Scalar): number {
  if (denominator.numerator === 0n) return 0.5;
  const top = numerator.numerator * denominator.denominator;
  const bottom = numerator.denominator * denominator.numerator;
  const precision = 1_000_000_000_000n;
  return Number((top * precision) / bottom) / Number(precision);
}

function resolveScaleModes(
  plotted: readonly ChartPoint[],
  x: string,
  y: string,
  hasY: boolean,
  xMode: ScaleMode,
  yMode: ScaleMode,
  xK: number,
  yK: number,
): readonly [ConcreteScaleMode, ConcreteScaleMode] {
  const xCandidates = xMode === "automatic" ? AUTOMATIC_CANDIDATES : [xMode];
  const yCandidates = !hasY
    ? ["linear" as const]
    : yMode === "automatic"
      ? AUTOMATIC_CANDIDATES
      : [yMode];
  const xValues = plotted.map((point) => point.values[x]!.scalar);
  const yValues = hasY ? plotted.map((point) => point.values[y]!.scalar) : [];
  let best: readonly [ConcreteScaleMode, ConcreteScaleMode] = [
    xCandidates[0]!,
    yCandidates[0]!,
  ];
  let bestScore = Number.POSITIVE_INFINITY;
  const transformedX = new Map<ConcreteScaleMode, number[]>();
  const transformedY = new Map<ConcreteScaleMode, number[]>();
  for (const candidateX of xCandidates) {
    const transformX = axisTransform(xValues, candidateX, xK);
    transformedX.set(
      candidateX,
      plotted.map((point) => scaleRatio(point.values[x]!.scalar, transformX)),
    );
  }
  for (const candidateY of yCandidates) {
    const transformY = axisTransform(yValues, candidateY, yK);
    transformedY.set(
      candidateY,
      hasY
        ? plotted.map((point) =>
            scaleRatio(point.values[y]!.scalar, transformY),
          )
        : plotted.map(() => 0.5),
    );
  }
  for (const candidateX of xCandidates) {
    for (const candidateY of yCandidates) {
      const occupied = new Map<string, number>();
      const xs = transformedX.get(candidateX)!;
      const ys = transformedY.get(candidateY)!;
      for (let index = 0; index < plotted.length; index += 1) {
        const key = `${Math.min(63, Math.floor(xs[index]! * 64))}:${Math.min(31, Math.floor(ys[index]! * 32))}`;
        occupied.set(key, (occupied.get(key) ?? 0) + 1);
      }
      const score = [...occupied.values()].reduce(
        (sum, count) => sum + (count * (count - 1)) / 2,
        0,
      );
      if (score < bestScore) {
        bestScore = score;
        best = [candidateX, candidateY];
      }
    }
  }
  return best;
}

function representativePoints(
  points: readonly ChartPoint[],
  x: string,
  y: string,
  hasY: boolean,
  xTransform: AxisTransform,
  yTransform: AxisTransform,
  layout: typeof PLOT_LAYOUT.compact | typeof PLOT_LAYOUT.expanded,
  level: VisualReductionLevel,
): ChartPoint[] {
  // The cell size follows the rendered symbol and axes. In source units its
  // width and height therefore change with each experiment and transformation.
  const cellSize = 2 * layout.dominatedRadius * REDUCTION_LEVEL_FACTOR[level];
  const cells = new Map<
    string,
    {
      count: number;
      sumX: number;
      sumY: number;
      representative: ChartPoint | null;
      distance: number;
    }
  >();
  const candidates: Array<{
    point: ChartPoint;
    x: number;
    y: number;
    key: string;
  }> = [];
  for (const point of points) {
    if (point.status !== "Dominado" || point.caseId === null) continue;
    const px =
      scaleRatio(point.values[x]!.scalar, xTransform) *
      (layout.right - layout.left);
    const py = hasY
      ? scaleRatio(point.values[y]!.scalar, yTransform) *
        (layout.bottom - layout.top)
      : 0;
    const key = `${Math.floor(px / cellSize)}:${Math.floor(py / cellSize)}`;
    const cell = cells.get(key);
    if (cell === undefined)
      cells.set(key, {
        count: 1,
        sumX: px,
        sumY: py,
        representative: null,
        distance: Infinity,
      });
    else {
      cell.count += 1;
      cell.sumX += px;
      cell.sumY += py;
    }
    candidates.push({ point, x: px, y: py, key });
  }
  for (const candidate of candidates) {
    const cell = cells.get(candidate.key)!;
    const dx = candidate.x - cell.sumX / cell.count;
    const dy = candidate.y - cell.sumY / cell.count;
    const distance = dx * dx + dy * dy;
    if (
      distance < cell.distance ||
      (distance === cell.distance &&
        candidate.point.caseId! < (cell.representative?.caseId ?? ""))
    ) {
      cell.distance = distance;
      cell.representative = candidate.point;
    }
  }
  const selected = new Set(
    [...cells.values()].map((cell) => cell.representative!.caseId),
  );
  return points.filter(
    (point) => point.status !== "Dominado" || selected.has(point.caseId),
  );
}

function exact(value: Exact | null | undefined): string {
  return value == null ? "—" : `${value.numerator}/${value.denominator}`;
}
function projectionRange(
  minimum: { numerator: number | string; denominator: number | string },
  maximum: { numerator: number | string; denominator: number | string },
): string {
  return `${formatFractionDecimal(minimum)}–${formatFractionDecimal(maximum)}`;
}
function dimensions(item: LayoutCaseResultV2): Record<string, Dimension> {
  const result: Record<string, Dimension> = {};
  const add = (id: string, scalar: Scalar | null, label: string) => {
    if (scalar !== null) result[id] = { scalar, label };
  };
  if (item.retained_layouts?.status === "conclusive")
    add(
      item.retained_layouts.objective_id,
      fraction(item.retained_layouts.fraction),
      formatFractionDecimal(item.retained_layouts.fraction),
    );
  for (const rel of item.rel_closeness ?? [])
    if (rel.status === "conclusive")
      add(rel.objective_id, fraction(rel.fraction), exact(rel.fraction));
  if (
    item.captured_flow?.status === "conclusive" &&
    item.captured_flow.total != null
  )
    add(
      item.captured_flow.objective_id,
      decimal(item.captured_flow.total),
      `${item.captured_flow.total} ${item.captured_flow.unit}/${item.captured_flow.horizon}`,
    );
  const adjacencyValues =
    (
      item as LayoutCaseResultV2 & {
        adjacency_values?: AdjacencyValueObservation[];
      }
    ).adjacency_values ?? [];
  for (const observation of adjacencyValues)
    if (observation.status === "conclusive" && observation.total != null)
      add(
        observation.objective_id,
        decimal(observation.total),
        `${observation.total} ${observation.unit}${observation.reference_period ? `/${observation.reference_period}` : ""}`,
      );
  return result;
}
function classification(item: LayoutCaseResultV2): string {
  if (item.feasibility !== "feasible") return "Inválido";
  if (item.pareto_classification.status !== "conclusive") return "Inconcluso";
  return item.pareto_classification.pareto_optimal ? "No dominado" : "Dominado";
}
function sortPoints(
  points: readonly Point[],
  sortKey: string,
  sortDirection: SortDirection,
): Point[] {
  return [...points].sort((left, right) => {
    let compared: number;
    if (sortKey === CASE_SORT)
      compared = left.item.case_id.localeCompare(right.item.case_id, "es", {
        numeric: true,
        sensitivity: "base",
      });
    else if (sortKey === COMPONENTS_SORT)
      compared = left.item.component_ids
        .join(", ")
        .localeCompare(right.item.component_ids.join(", "), "es", {
          numeric: true,
          sensitivity: "base",
        });
    else if (sortKey === CLASSIFICATION_SORT)
      compared = classification(left.item).localeCompare(
        classification(right.item),
        "es",
      );
    else {
      const objective = sortKey.slice("objective:".length);
      const leftValue = left.values[objective]?.scalar;
      const rightValue = right.values[objective]?.scalar;
      if (leftValue === undefined || rightValue === undefined)
        return leftValue === undefined
          ? rightValue === undefined
            ? 0
            : 1
          : -1;
      compared = compareScalar(leftValue, rightValue);
    }
    return sortDirection === "ascending" ? compared : -compared;
  });
}
function groupEquivalentCases(
  cases: readonly LayoutCaseResultV2[],
): Array<{
  item: LayoutCaseResultV2;
  equivalents: readonly LayoutCaseResultV2[];
}> {
  const groups = new Map<string, LayoutCaseResultV2[]>();
  for (const item of cases) {
    const group = groups.get(item.forest_id) ?? [];
    group.push(item);
    groups.set(item.forest_id, group);
  }
  return [...groups.values()].map((equivalents) => {
    equivalents.sort((left, right) => {
      const bySize =
        left.added_component_ids.length - right.added_component_ids.length;
      return bySize !== 0
        ? bySize
        : left.added_component_ids
            .join("\0")
            .localeCompare(right.added_component_ids.join("\0"), "es");
    });
    return { item: equivalents[0]!, equivalents };
  });
}
function ExpandIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8.5 3.5h-5v5M15.5 3.5h5v5M8.5 20.5h-5v-5M15.5 20.5h5v-5" />
    </svg>
  );
}
export function CaseDetailButton({
  item,
  equivalents,
  loading = false,
  disabled = false,
  onSelect,
}: {
  item: LayoutCaseResultV2;
  equivalents: readonly LayoutCaseResultV2[];
  loading?: boolean;
  disabled?: boolean;
  onSelect: (
    item: LayoutCaseResultV2,
    equivalents: readonly LayoutCaseResultV2[],
  ) => void;
}) {
  return (
    <ActionIconButton
      action="view-details"
      label="Ver detalle"
      className="srfl-detail-button"
      loading={loading}
      disabled={disabled}
      onClick={() => onSelect(item, equivalents)}
    />
  );
}

function AxisSelectors({
  refs,
  aliases,
  x,
  y,
  changeX,
  changeY,
}: {
  refs: readonly string[];
  aliases: Readonly<Record<string, string>>;
  x: string;
  y: string;
  changeX: (value: string) => void;
  changeY: (value: string) => void;
}) {
  if (refs.length < 2) return null;
  return (
    <div className="srfl-chart-controls">
      <SelectField
        label="Eje X"
        aria-label="Eje X"
        value={x}
        options={refs.map((ref) => ({
          value: ref,
          label: aliases[ref] ?? ref,
          disabled: ref === y,
        }))}
        onChange={(event) => changeX(event.target.value)}
      />
      <SelectField
        label="Eje Y"
        aria-label="Eje Y"
        value={y}
        options={refs.map((ref) => ({
          value: ref,
          label: aliases[ref] ?? ref,
          disabled: ref === x,
        }))}
        onChange={(event) => changeY(event.target.value)}
      />
    </div>
  );
}

const SCALE_OPTIONS = [
  { value: "automatic", label: "Automática" },
  { value: "linear", label: "Lineal" },
  { value: "square-root", label: "Raíz cuadrada" },
  { value: "adjusted-log", label: "Logarítmica ajustada" },
  { value: "percentile", label: "Percentiles" },
] as const;

function ScaleControls({
  hasY,
  xScale,
  yScale,
  xLogK,
  yLogK,
  setXScale,
  setYScale,
  setXLogK,
  setYLogK,
}: {
  hasY: boolean;
  xScale: ScaleMode;
  yScale: ScaleMode;
  xLogK: string;
  yLogK: string;
  setXScale: (value: ScaleMode) => void;
  setYScale: (value: ScaleMode) => void;
  setXLogK: (value: string) => void;
  setYLogK: (value: string) => void;
}) {
  return (
    <div className="srfl-scale-controls">
      <SelectField
        label="Transformación X"
        aria-label="Transformación X"
        value={xScale}
        options={SCALE_OPTIONS}
        onChange={(event) => setXScale(event.target.value as ScaleMode)}
      />
      {xScale === "adjusted-log" && (
        <NumberField
          label="k X"
          aria-label="k X"
          min="0.000001"
          step="any"
          value={xLogK}
          onChange={(event) => setXLogK(event.target.value)}
        />
      )}
      {hasY && (
        <SelectField
          label="Transformación Y"
          aria-label="Transformación Y"
          value={yScale}
          options={SCALE_OPTIONS}
          onChange={(event) => setYScale(event.target.value as ScaleMode)}
        />
      )}
      {hasY && yScale === "adjusted-log" && (
        <NumberField
          label="k Y"
          aria-label="k Y"
          min="0.000001"
          step="any"
          value={yLogK}
          onChange={(event) => setYLogK(event.target.value)}
        />
      )}
    </div>
  );
}

function ParetoPlot({
  plotted,
  axisContext,
  frontier,
  refs,
  aliases,
  x,
  y,
  showFrontier,
  expanded,
  xScale,
  yScale,
  xLogK,
  yLogK,
  projectionAxes,
  onSelectCaseId,
}: {
  plotted: readonly ChartPoint[];
  axisContext?: AxisContext;
  frontier: readonly ChartPoint[];
  refs: readonly string[];
  aliases: Readonly<Record<string, string>>;
  x: string;
  y: string;
  showFrontier: boolean;
  expanded: boolean;
  xScale: ScaleMode;
  yScale: ScaleMode;
  xLogK: number;
  yLogK: number;
  projectionAxes?: PlotProjectionResult["axes"];
  onSelectCaseId?: (caseId: string) => void;
}) {
  const layout = expanded ? PLOT_LAYOUT.expanded : PLOT_LAYOUT.compact;
  const { width, height, left, right, top, bottom } = layout;
  const hasY = refs.length > 1;
  const [resolvedXScale, resolvedYScale] = useMemo(
    () =>
      axisContext?.modes ??
      resolveScaleModes(plotted, x, y, hasY, xScale, yScale, xLogK, yLogK),
    [axisContext, hasY, plotted, x, xLogK, xScale, y, yLogK, yScale],
  );
  const effectiveXScale = projectionAxes?.x.scale ?? resolvedXScale;
  const effectiveYScale = projectionAxes?.y.scale ?? resolvedYScale;
  const xTransform = useMemo(
    () =>
      axisContext?.x ??
      axisTransform(
        plotted.map((point) => point.values[x]!.scalar),
        effectiveXScale,
        xLogK,
      ),
    [axisContext, effectiveXScale, plotted, x, xLogK],
  );
  const yTransform = useMemo(
    () =>
      axisContext?.y ??
      axisTransform(
        hasY ? plotted.map((point) => point.values[y]!.scalar) : [],
        effectiveYScale,
        yLogK,
      ),
    [axisContext, effectiveYScale, hasY, plotted, y, yLogK],
  );
  const coordinate = (
    value: Scalar,
    start: number,
    end: number,
    transform: AxisTransform,
  ) => {
    return start + scaleRatio(value, transform) * (end - start);
  };
  const position = (
    values: Record<string, Dimension>,
    projected?: { x: number; y: number },
  ) =>
    projected !== undefined
      ? {
          x: left + projected.x * (right - left),
          y: bottom - projected.y * (bottom - top),
        }
      : {
          x: coordinate(values[x]!.scalar, left, right, xTransform),
          y: !hasY
            ? (top + bottom) / 2
            : coordinate(values[y]!.scalar, bottom, top, yTransform),
        };
  if (plotted.length === 0)
    return (
      <p>No hay observaciones concluyentes para los ejes seleccionados.</p>
    );
  const ticks = expanded ? [0, 0.2, 0.4, 0.6, 0.8, 1] : [];
  const xLabel = aliases[x] ?? x;
  const yLabel = aliases[y] ?? y;
  return (
    <svg
      className={expanded ? "is-expanded" : ""}
      data-x-scale={effectiveXScale}
      data-y-scale={hasY ? effectiveYScale : undefined}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={
        refs.length === 1
          ? `Eje ${xLabel}`
          : `Proyección ${xLabel} por ${yLabel}`
      }
    >
      {ticks.map((ratio) => (
        <g className="srfl-chart-grid" key={ratio}>
          <line
            x1={left + (right - left) * ratio}
            y1={top}
            x2={left + (right - left) * ratio}
            y2={bottom}
          />
          <text
            className="srfl-axis-tick"
            x={left + (right - left) * ratio}
            y={bottom + 24}
          >
            {projectionAxes?.x.ticks.find((tick) => tick.position === ratio)
              ?.label ?? formatTick(tickValue(ratio, xTransform))}
          </text>
          {hasY && (
            <>
              <line
                x1={left}
                y1={bottom - (bottom - top) * ratio}
                x2={right}
                y2={bottom - (bottom - top) * ratio}
              />
              <text
                className="srfl-axis-tick srfl-axis-tick--y"
                x={left - 12}
                y={bottom - (bottom - top) * ratio + 4}
              >
                {projectionAxes?.y.ticks.find((tick) => tick.position === ratio)
                  ?.label ?? formatTick(tickValue(ratio, yTransform))}
              </text>
            </>
          )}
        </g>
      ))}
      <line x1={left} y1={top} x2={left} y2={bottom} />
      <line x1={left} y1={bottom} x2={right} y2={bottom} />
      <text x={(left + right) / 2} y={height - 18}>
        {xLabel}
      </text>
      {hasY && (
        <text
          x="24"
          y={(top + bottom) / 2}
          transform={`rotate(-90 24 ${(top + bottom) / 2})`}
        >
          {yLabel}
        </text>
      )}
      {showFrontier && frontier.length > 1 && (
        <polyline
          className="srfl-pareto-frontier"
          points={frontier
            .map(({ values, position: projected }) => {
              const point = position(values, projected);
              return `${point.x},${point.y}`;
            })
            .join(" ")}
        />
      )}
      {plotted.map(({ caseId, status, values, position: projected, group }) => {
        const point = position(values, projected);
        const xv = values[x];
        const yv = refs.length === 1 ? undefined : values[y];
        const label =
          group !== undefined
            ? `${group.count} ${group.count === 1 ? "alternativa dominada" : "alternativas dominadas"}; ${xLabel} entre ${projectionRange(group.x_min, group.x_max)}; ${yLabel} entre ${projectionRange(group.y_min, group.y_max)}`
            : `${caseId ?? "Alternativa"}: ${status}; ${xLabel} ${xv?.label ?? ""}${yv === undefined ? "" : `; ${yLabel} ${yv.label}`}`;
        const selectable = caseId !== null;
        const key = caseId ?? `group-${group?.x}-${group?.y}-${group?.count}`;
        return (
          <g
            key={key}
            tabIndex={selectable ? 0 : undefined}
            role={selectable ? "button" : undefined}
            aria-label={selectable ? label : undefined}
            onClick={selectable ? () => onSelectCaseId?.(caseId) : undefined}
            onKeyDown={(event) => {
              if (selectable && (event.key === "Enter" || event.key === " ")) {
                event.preventDefault();
                onSelectCaseId?.(caseId!);
              }
            }}
          >
            <title>{label}</title>
            {group !== undefined && group.count > 1 ? (
              <>
                <path
                  className="srfl-point-group"
                  d={`M ${point.x} ${point.y - 9} L ${point.x + 9} ${point.y} L ${point.x} ${point.y + 9} L ${point.x - 9} ${point.y} Z`}
                />
                <text
                  className="srfl-point-group-count"
                  x={point.x}
                  y={point.y + 3}
                >
                  {group.count}
                </text>
              </>
            ) : (
              <circle
                className="srfl-point-hitbox"
                cx={point.x}
                cy={point.y}
                r={expanded ? 12 : 8}
              />
            )}
            {group !== undefined && group.count > 1 ? null : status ===
              "No dominado" ? (
              <rect
                className="is-pareto"
                x={point.x - (expanded ? 6 : 5)}
                y={point.y - (expanded ? 6 : 5)}
                width={expanded ? 12 : 10}
                height={expanded ? 12 : 10}
              />
            ) : status === "Dominado" ? (
              <circle
                className="is-dominated"
                cx={point.x}
                cy={point.y}
                r={layout.dominatedRadius}
              />
            ) : (
              <path
                className="is-inconclusive"
                d={`M ${point.x} ${point.y - 5} L ${point.x + 5} ${point.y + 4} L ${point.x - 5} ${point.y + 4} Z`}
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}

export function IndexedParetoChart({
  objectives,
  frontierCases,
  loadPoints,
  loadProjection,
  visualNoiseReductionAvailable = false,
  onSelectCaseId,
}: {
  objectives: readonly { id: string; label: string }[];
  frontierCases: readonly LayoutCaseResultV2[];
  loadPoints: (x: string, y: string) => Promise<readonly SrflPlotPoint[]>;
  loadProjection?: (
    x: string,
    y: string,
    xScale: ScaleMode,
    yScale: ScaleMode,
    xLogK: number,
    yLogK: number,
    level: 0 | 1 | 2,
    section: "groups" | "frontier_positions",
  ) => Promise<PlotProjectionResult>;
  visualNoiseReductionAvailable?: boolean;
  onSelectCaseId: (caseId: string) => void;
}) {
  const refs = objectives.map((item) => item.id);
  const aliases = Object.fromEntries(
    objectives.map((item) => [item.id, item.label]),
  );
  const [x, setX] = useState(refs[0] ?? "");
  const [y, setY] = useState(refs[1] ?? refs[0] ?? "");
  const [points, setPoints] = useState<readonly SrflPlotPoint[]>([]);
  const [groups, setGroups] = useState<readonly PlotProjectionGroup[]>([]);
  const [frontierPositions, setFrontierPositions] = useState<
    readonly FrontierProjectionPoint[]
  >([]);
  const [projectionAxes, setProjectionAxes] = useState<
    PlotProjectionResult["axes"] | undefined
  >();
  const [level, setLevel] = useState<0 | 1 | 2>(0);
  const [loading, setLoading] = useState(false);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [frontierLoading, setFrontierLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showFrontier, setShowFrontier] = useState(true);
  const [reduceVisualNoise, setReduceVisualNoise] = useState(false);
  const [reductionLevel, setReductionLevel] =
    useState<VisualReductionLevel>("medium");
  const [expanded, setExpanded] = useState(false);
  const [xScale, setXScale] = useState<ScaleMode>("automatic");
  const [yScale, setYScale] = useState<ScaleMode>("automatic");
  const [xLogK, setXLogK] = useState("100");
  const [yLogK, setYLogK] = useState("100");
  useEffect(() => {
    setX(refs[0] ?? "");
    setY(refs[1] ?? refs[0] ?? "");
  }, [refs.join("\0")]);
  useEffect(() => {
    if (x === "" || y === "" || loadProjection === undefined) return;
    let active = true;
    setProjectionAxes(undefined);
    setFrontierPositions([]);
    setGroups([]);
    setError(null);
    setFrontierLoading(true);
    void loadProjection(
      x,
      y,
      xScale,
      yScale,
      positiveNumber(xLogK, 100),
      positiveNumber(yLogK, 100),
      0,
      "frontier_positions",
    )
      .then((loaded) => {
        if (!active) return;
        setProjectionAxes(loaded.axes);
        setFrontierPositions(
          loaded.items as readonly FrontierProjectionPoint[],
        );
      })
      .catch((reason: unknown) => {
        if (active) setError(String(reason));
      })
      .finally(() => {
        if (active) setFrontierLoading(false);
      });
    return () => {
      active = false;
    };
  }, [loadProjection, x, y, xScale, yScale, xLogK, yLogK]);
  useEffect(() => {
    if (x === "" || y === "" || loadProjection === undefined) return;
    let active = true;
    setError(null);
    setGroups([]);
    setGroupsLoading(true);
    void loadProjection(
      x,
      y,
      xScale,
      yScale,
      positiveNumber(xLogK, 100),
      positiveNumber(yLogK, 100),
      level,
      "groups",
    )
      .then((loaded) => {
        if (!active) return;
        setGroups(loaded.items as readonly PlotProjectionGroup[]);
      })
      .catch((reason: unknown) => {
        if (active) setError(String(reason));
      })
      .finally(() => {
        if (active) setGroupsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [loadProjection, x, y, xScale, yScale, xLogK, yLogK, level]);
  useEffect(() => {
    if (x === "" || y === "" || loadProjection !== undefined) return;
    let active = true;
    setPoints([]);
    setLoading(true);
    setError(null);
    void loadPoints(x, y)
      .then((loaded) => {
        if (active) setPoints(loaded);
      })
      .catch((reason: unknown) => {
        if (active) setError(String(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [loadProjection, loadPoints, x, y]);
  const directFrontier = frontierCases.flatMap((item) => {
    const values = dimensions(item);
    if (values[x] === undefined || (refs.length > 1 && values[y] === undefined))
      return [];
    return [{ caseId: item.case_id, status: "No dominado", values }];
  });
  const frontierIds = useMemo(
    () => new Set(frontierCases.map((item) => item.case_id)),
    [frontierCases],
  );
  const groupedPoints: ChartPoint[] = groups.map((group) => ({
    caseId: group.count === 1 ? (group.case_id ?? null) : null,
    status: "Dominado",
    values: {
      [x]: { scalar: ZERO, label: "" },
      [y]: { scalar: ZERO, label: "" },
    },
    position: { x: group.x, y: group.y },
    group,
  }));
  const positionedFrontier: ChartPoint[] = frontierPositions.flatMap(
    (projected) => {
      const item = frontierCases.find(
        (candidate) => candidate.case_id === projected.case_id,
      );
      if (item === undefined) return [];
      const values = dimensions(item);
      if (
        values[x] === undefined ||
        (refs.length > 1 && values[y] === undefined)
      )
        return [];
      return [
        {
          caseId: projected.case_id,
          status: "No dominado",
          values,
          position: { x: projected.x, y: projected.y },
        },
      ];
    },
  );
  const chartPoints: ChartPoint[] =
    loadProjection !== undefined && projectionAxes !== undefined
      ? [...groupedPoints, ...positionedFrontier]
      : directFrontier;
  const standardPoints = useMemo(
    () =>
      points.flatMap((point) => {
        const xScalar = fraction(point.x);
        const yScalar = fraction(point.y);
        if (xScalar === null || (refs.length > 1 && yScalar === null))
          return [];
        const values: Record<string, Dimension> = {
          [x]: {
            scalar: xScalar,
            label: `${xScalar.numerator}/${xScalar.denominator}`,
          },
        };
        if (yScalar !== null)
          values[y] = {
            scalar: yScalar,
            label: `${yScalar.numerator}/${yScalar.denominator}`,
          };
        const nonDominated = frontierIds.has(point.case_id);
        return [
          {
            caseId: point.case_id,
            status: nonDominated
              ? "No dominado"
              : frontierCases.length === 0
                ? "Inconcluso"
                : "Dominado",
            values,
          },
        ];
      }),
    [points, x, y, refs.length, frontierIds, frontierCases.length],
  );
  const exactPoints =
    standardPoints.length === 0 ? directFrontier : standardPoints;
  const reductionTransforms = useMemo(() => {
    if (
      !visualNoiseReductionAvailable ||
      !reduceVisualNoise ||
      loadProjection !== undefined ||
      standardPoints.length === 0
    )
      return null;
    const hasY = refs.length > 1;
    const [effectiveX, effectiveY] = resolveScaleModes(
      standardPoints,
      x,
      y,
      hasY,
      xScale,
      yScale,
      positiveNumber(xLogK, 100),
      positiveNumber(yLogK, 100),
    );
    return {
      modes: [effectiveX, effectiveY] as const,
      x: axisTransform(
        standardPoints.map((point) => point.values[x]!.scalar),
        effectiveX,
        positiveNumber(xLogK, 100),
      ),
      y: axisTransform(
        hasY ? standardPoints.map((point) => point.values[y]!.scalar) : [],
        effectiveY,
        positiveNumber(yLogK, 100),
      ),
    };
  }, [
    visualNoiseReductionAvailable,
    reduceVisualNoise,
    loadProjection,
    standardPoints,
    refs.length,
    x,
    y,
    xScale,
    yScale,
    xLogK,
    yLogK,
  ]);
  const compactRepresentatives = useMemo(
    () =>
      reductionTransforms === null
        ? null
        : representativePoints(
            standardPoints,
            x,
            y,
            refs.length > 1,
            reductionTransforms.x,
            reductionTransforms.y,
            PLOT_LAYOUT.compact,
            reductionLevel,
          ),
    [reductionTransforms, standardPoints, x, y, refs.length, reductionLevel],
  );
  const expandedRepresentatives = useMemo(
    () =>
      !expanded || reductionTransforms === null
        ? null
        : representativePoints(
            standardPoints,
            x,
            y,
            refs.length > 1,
            reductionTransforms.x,
            reductionTransforms.y,
            PLOT_LAYOUT.expanded,
            reductionLevel,
          ),
    [
      expanded,
      reductionTransforms,
      standardPoints,
      x,
      y,
      refs.length,
      reductionLevel,
    ],
  );
  const frontier = (
    loadProjection === undefined
      ? exactPoints.filter(
          (point) => point.caseId !== null && frontierIds.has(point.caseId),
        )
      : chartPoints.filter((point) => point.status === "No dominado")
  ).sort((left, right) =>
    compareScalar(
      left.values[x]?.scalar ?? ZERO,
      right.values[x]?.scalar ?? ZERO,
    ),
  );
  const plotted = loadProjection === undefined ? exactPoints : chartPoints;
  const resetProjection = () => {
    setLevel(0);
    setProjectionAxes(undefined);
    setGroups([]);
    setFrontierPositions([]);
  };
  const changeX = (value: string) => {
    setX(value);
    resetProjection();
    if (value === y) setY(refs.find((ref) => ref !== value) ?? value);
  };
  const changeY = (value: string) => {
    setY(value);
    resetProjection();
    if (value === x) setX(refs.find((ref) => ref !== value) ?? value);
  };
  const updateXScale = (value: ScaleMode) => {
    setXScale(value);
    resetProjection();
  };
  const updateYScale = (value: ScaleMode) => {
    setYScale(value);
    resetProjection();
  };
  const updateXK = (value: string) => {
    setXLogK(value);
    resetProjection();
  };
  const updateYK = (value: string) => {
    setYLogK(value);
    resetProjection();
  };
  const plot = (isExpanded: boolean) => (
    <ParetoPlot
      plotted={
        (isExpanded ? expandedRepresentatives : compactRepresentatives) ??
        plotted
      }
      axisContext={reductionTransforms ?? undefined}
      frontier={frontier}
      refs={refs}
      aliases={aliases}
      x={x}
      y={y}
      showFrontier={showFrontier}
      expanded={isExpanded}
      xScale={
        loadProjection !== undefined && projectionAxes === undefined
          ? "linear"
          : xScale
      }
      yScale={
        loadProjection !== undefined && projectionAxes === undefined
          ? "linear"
          : yScale
      }
      xLogK={positiveNumber(xLogK, 100)}
      yLogK={positiveNumber(yLogK, 100)}
      projectionAxes={loadProjection === undefined ? undefined : projectionAxes}
      onSelectCaseId={onSelectCaseId}
    />
  );
  const reductionToggle = () =>
    visualNoiseReductionAvailable &&
    loadProjection === undefined && (
      <label className="srfl-frontier-toggle">
        <input
          type="checkbox"
          checked={reduceVisualNoise}
          onChange={(event) => setReduceVisualNoise(event.target.checked)}
        />{" "}
        Reducir el ruido visual
      </label>
    );
  const reductionSelector = () =>
    visualNoiseReductionAvailable &&
    reduceVisualNoise &&
    loadProjection === undefined && (
      <div className="srfl-chart-controls">
        <SelectField
          label="Nivel de reducción"
          aria-label="Nivel de reducción"
          value={reductionLevel}
          options={[
            { value: "low", label: "Bajo" },
            { value: "medium", label: "Medio" },
            { value: "high", label: "Alto" },
          ]}
          onChange={(event) =>
            setReductionLevel(event.target.value as VisualReductionLevel)
          }
        />
      </div>
    );
  if (refs.length === 0)
    return <p>Se requiere al menos un criterio para proyectar el gráfico.</p>;
  return (
    <section
      className="srfl-result-chart"
      aria-label="Gráfico de la frontera de Pareto"
    >
      <header>
        <div>
          <h3>Proyección de la frontera</h3>
          <p>
            La frontera procede de la clasificación exacta confirmada por
            Python.
          </p>
        </div>
        <div className="srfl-chart-actions">
          {frontier.length > 1 && (
            <label className="srfl-frontier-toggle">
              <input
                type="checkbox"
                checked={showFrontier}
                onChange={(event) => setShowFrontier(event.target.checked)}
              />{" "}
              Trazar frente
            </label>
          )}
          {reductionToggle()}
          <IconButton label="Ampliar gráfico" onClick={() => setExpanded(true)}>
            <ExpandIcon />
          </IconButton>
        </div>
      </header>
      <AxisSelectors
        refs={refs}
        aliases={aliases}
        x={x}
        y={y}
        changeX={changeX}
        changeY={changeY}
      />
      <ScaleControls
        hasY
        xScale={xScale}
        yScale={yScale}
        xLogK={xLogK}
        yLogK={yLogK}
        setXScale={updateXScale}
        setYScale={updateYScale}
        setXLogK={updateXK}
        setYLogK={updateYK}
      />
      {reductionSelector()}
      {loadProjection !== undefined && projectionAxes === undefined && (
        <p role="status">
          Preparando alternativas dominadas; la frontera usa ejes lineales
          provisorios…
        </p>
      )}
      {loadProjection === undefined && loading && (
        <p role="status">Cargando puntos del gráfico…</p>
      )}
      {compactRepresentatives !== null && (
        <p className="srfl-chart-filter-summary">
          Mostrando {compactRepresentatives.length} de {standardPoints.length}{" "}
          puntos proyectables. La frontera permanece completa.
        </p>
      )}
      {plot(false)}
      {loadProjection !== undefined && groupsLoading && (
        <p role="status">Actualizando agrupaciones…</p>
      )}
      {loadProjection !== undefined && (
        <div className="srfl-projection-controls">
          <span>
            Nivel {level} ·{" "}
            {level === 0 ? "16 × 8" : level === 1 ? "32 × 16" : "64 × 32"}
          </span>
          <button
            type="button"
            disabled={
              groupsLoading ||
              frontierLoading ||
              projectionAxes === undefined ||
              level === 2
            }
            onClick={() =>
              setLevel((value) => Math.min(2, value + 1) as 0 | 1 | 2)
            }
          >
            Mostrar más detalle
          </button>
        </div>
      )}
      {error !== null && (
        <p role="alert">No se pudieron cargar los puntos: {error}</p>
      )}
      {expanded && (
        <Modal
          title="Explorador de la frontera de Pareto"
          className="srfl-chart-modal"
          backdropClassName="srfl-chart-backdrop"
          onClose={() => setExpanded(false)}
        >
          <div className="srfl-expanded-toolbar">
            <div>
              <AxisSelectors
                refs={refs}
                aliases={aliases}
                x={x}
                y={y}
                changeX={changeX}
                changeY={changeY}
              />
              <ScaleControls
                hasY
                xScale={xScale}
                yScale={yScale}
                xLogK={xLogK}
                yLogK={yLogK}
                setXScale={updateXScale}
                setYScale={updateYScale}
                setXLogK={updateXK}
                setYLogK={updateYK}
              />
              {reductionToggle()}
              {reductionSelector()}
            </div>
          </div>
          <div className="srfl-chart-expanded">
            {expandedRepresentatives !== null && (
              <p className="srfl-chart-filter-summary">
                Mostrando {expandedRepresentatives.length} de{" "}
                {standardPoints.length} puntos proyectables. La frontera
                permanece completa.
              </p>
            )}
            {plot(true)}
          </div>
        </Modal>
      )}
    </section>
  );
}

export function DesignComparison({
  cases,
  objectiveAliases = {},
  onSelect,
}: {
  cases: readonly LayoutCaseResultV2[];
  objectiveAliases?: Readonly<Record<string, string>>;
  onSelect: (
    item: LayoutCaseResultV2,
    equivalents: readonly LayoutCaseResultV2[],
  ) => void;
}) {
  const refs = cases[0]?.pareto_classification.objective_refs ?? [];
  const [x, setX] = useState(refs[0] ?? "");
  const [y, setY] = useState(refs[1] ?? refs[0] ?? "");
  const [showFrontier, setShowFrontier] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [xScale, setXScale] = useState<ScaleMode>("automatic");
  const [yScale, setYScale] = useState<ScaleMode>("automatic");
  const [xLogK, setXLogK] = useState("100");
  const [yLogK, setYLogK] = useState("100");
  const [sortKey, setSortKey] = useState(CASE_SORT);
  const [sortDirection, setSortDirection] =
    useState<SortDirection>("ascending");
  const [tablePage, setTablePage] = useState(0);
  const [paretoSortKey, setParetoSortKey] = useState(CASE_SORT);
  const [paretoSortDirection, setParetoSortDirection] =
    useState<SortDirection>("ascending");
  useEffect(() => {
    setX(refs[0] ?? "");
    setY(refs[1] ?? refs[0] ?? "");
  }, [refs.join("\0")]);
  const changeX = (value: string) => {
    setX(value);
    if (value === y) setY(refs.find((ref) => ref !== value) ?? value);
  };
  const changeY = (value: string) => {
    setY(value);
    if (value === x) setX(refs.find((ref) => ref !== value) ?? value);
  };
  const points = useMemo(
    () =>
      groupEquivalentCases(cases).map(({ item, equivalents }) => ({
        item,
        equivalents,
        values: dimensions(item),
      })),
    [cases],
  );
  const validPoints = useMemo(
    () => points.filter(({ item }) => item.feasibility === "feasible"),
    [points],
  );
  const paretoPoints = useMemo(
    () =>
      validPoints.filter(
        ({ item }) =>
          item.pareto_classification.status === "conclusive" &&
          item.pareto_classification.pareto_optimal === true,
      ),
    [validPoints],
  );
  const plotted = useMemo(
    () =>
      validPoints.filter(
        ({ values }) =>
          values[x] !== undefined &&
          (refs.length === 1 || values[y] !== undefined),
      ),
    [refs.length, validPoints, x, y],
  );
  const frontier = useMemo(
    () =>
      plotted
        .filter(
          ({ item }) =>
            item.pareto_classification.status === "conclusive" &&
            item.pareto_classification.pareto_optimal === true,
        )
        .sort((left, right) => {
          const comparedX = compareScalar(
            left.values[x]!.scalar,
            right.values[x]!.scalar,
          );
          return comparedX !== 0 || refs.length === 1
            ? comparedX
            : compareScalar(left.values[y]!.scalar, right.values[y]!.scalar);
        }),
    [plotted, refs.length, x, y],
  );
  const changeSort = (key: string) => {
    setTablePage(0);
    if (key === sortKey)
      setSortDirection((current) =>
        current === "ascending" ? "descending" : "ascending",
      );
    else {
      setSortKey(key);
      setSortDirection("ascending");
    }
  };
  const changeParetoSort = (key: string) => {
    if (key === paretoSortKey)
      setParetoSortDirection((current) =>
        current === "ascending" ? "descending" : "ascending",
      );
    else {
      setParetoSortKey(key);
      setParetoSortDirection("ascending");
    }
  };
  const sorted = useMemo(
    () => sortPoints(validPoints, sortKey, sortDirection),
    [sortDirection, sortKey, validPoints],
  );
  const pageSize = 50;
  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const tableRows = sorted.slice(
    tablePage * pageSize,
    (tablePage + 1) * pageSize,
  );
  const sortedParetoPoints = useMemo(
    () => sortPoints(paretoPoints, paretoSortKey, paretoSortDirection),
    [paretoPoints, paretoSortDirection, paretoSortKey],
  );
  const sortHeader = (key: string, label: string) => (
    <th key={key} aria-sort={sortKey === key ? sortDirection : "none"}>
      <button
        type="button"
        className="srfl-sort-button"
        onClick={() => changeSort(key)}
      >
        {label}
        <span aria-hidden="true">
          {sortKey === key
            ? sortDirection === "ascending"
              ? " ↑"
              : " ↓"
            : " ↕"}
        </span>
      </button>
    </th>
  );
  const paretoSortHeader = (key: string, label: string) => (
    <th
      key={key}
      aria-sort={paretoSortKey === key ? paretoSortDirection : "none"}
    >
      <button
        type="button"
        className="srfl-sort-button"
        onClick={() => changeParetoSort(key)}
      >
        {label}
        <span aria-hidden="true">
          {paretoSortKey === key
            ? paretoSortDirection === "ascending"
              ? " ↑"
              : " ↓"
            : " ↕"}
        </span>
      </button>
    </th>
  );
  const plot = (isExpanded: boolean) => (
    <ParetoPlot
      plotted={plotted.map(({ item, values }) => ({
        caseId: item.case_id,
        status: classification(item),
        values,
      }))}
      frontier={frontier.map(({ item, values }) => ({
        caseId: item.case_id,
        status: classification(item),
        values,
      }))}
      refs={refs}
      aliases={objectiveAliases}
      x={x}
      y={y}
      showFrontier={showFrontier}
      expanded={isExpanded}
      xScale={xScale}
      yScale={yScale}
      xLogK={positiveNumber(xLogK, 100)}
      yLogK={positiveNumber(yLogK, 100)}
      onSelectCaseId={(caseId) => {
        const found = plotted.find((point) => point.item.case_id === caseId);
        if (found !== undefined) onSelect(found.item, found.equivalents);
      }}
    />
  );

  return (
    <section className="srfl-pareto-explorer" aria-label="Explorador Pareto">
      <section
        id="resultado-pareto"
        className="srfl-pareto-summary"
        aria-label="Resumen de casos no dominados"
      >
        <header>
          <h3>Casos no dominados</h3>
          <p>
            {paretoPoints.length} de {validPoints.length} alternativas físicas
            pertenecen a la frontera global calculada.
          </p>
        </header>
        {paretoPoints.length === 0 ? (
          <p>No hay una frontera concluyente para este diseño.</p>
        ) : (
          <div className="ui-table-wrap">
            <table className="ui-table">
              <thead>
                <tr>
                  {paretoSortHeader(CASE_SORT, "Caso")}
                  {refs.map((ref) =>
                    paretoSortHeader(
                      objectiveSort(ref),
                      objectiveAliases[ref] ?? ref,
                    ),
                  )}
                  <th>
                    <span className="sr-only">Acción</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedParetoPoints.map(({ item, values, equivalents }) => (
                  <tr key={item.case_id}>
                    <td>
                      <strong>{item.case_id.slice(0, 12)}</strong>
                      <small>
                        {item.component_ids.join(", ") || "Sin componentes"}
                      </small>
                      {equivalents.length > 1 && (
                        <small>
                          {equivalents.length} selecciones equivalentes
                        </small>
                      )}
                    </td>
                    {refs.map((ref) => (
                      <td key={ref}>{values[ref]?.label ?? "Inconcluso"}</td>
                    ))}
                    <td>
                      <CaseDetailButton
                        item={item}
                        equivalents={equivalents}
                        onSelect={onSelect}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section
        id="resultado-grafico"
        className="srfl-result-chart"
        aria-label="Gráfico de la frontera de Pareto"
      >
        <header>
          <div>
            <h3>Proyección de la frontera</h3>
            <p>
              Vista previa. La línea une casos no dominados en los ejes visibles
              y no recalcula la clasificación global.
            </p>
          </div>
          <div className="srfl-chart-actions">
            {frontier.length > 1 && (
              <label className="srfl-frontier-toggle">
                <input
                  type="checkbox"
                  checked={showFrontier}
                  onChange={(event) => setShowFrontier(event.target.checked)}
                />{" "}
                Trazar frente
              </label>
            )}
            <IconButton
              label="Ampliar gráfico"
              onClick={() => setExpanded(true)}
            >
              <ExpandIcon />
            </IconButton>
          </div>
        </header>
        <AxisSelectors
          refs={refs}
          aliases={objectiveAliases}
          x={x}
          y={y}
          changeX={changeX}
          changeY={changeY}
        />
        <ScaleControls
          hasY={refs.length > 1}
          xScale={xScale}
          yScale={yScale}
          xLogK={xLogK}
          yLogK={yLogK}
          setXScale={setXScale}
          setYScale={setYScale}
          setXLogK={setXLogK}
          setYLogK={setYLogK}
        />
        {plot(false)}
      </section>
      <section
        id="resultado-tabla"
        className="srfl-all-cases"
        aria-label="Todos los casos válidos"
      >
        <header>
          <h3>Todos los casos válidos</h3>
          <p>
            Seleccioná cualquier encabezado para ordenar en forma ascendente o
            descendente. Las selecciones que producen la misma disposición de
            restricciones se muestran una sola vez.
          </p>
        </header>
        <div className="ui-table-wrap">
          <table className="ui-table">
            <thead>
              <tr>
                {sortHeader(CASE_SORT, "Caso")}
                {sortHeader(COMPONENTS_SORT, "Componentes")}
                {refs.map((ref) =>
                  sortHeader(objectiveSort(ref), objectiveAliases[ref] ?? ref),
                )}
                {sortHeader(CLASSIFICATION_SORT, "Clasificación")}
                <th>
                  <span className="sr-only">Acción</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {tableRows.map(({ item, values, equivalents }) => (
                <tr key={item.case_id}>
                  <td>{item.case_id.slice(0, 12)}</td>
                  <td>
                    {item.component_ids.join(", ") || "—"}
                    {equivalents.length > 1 && (
                      <small className="srfl-equivalent-count">
                        {equivalents.length} selecciones equivalentes
                      </small>
                    )}
                  </td>
                  {refs.map((ref) => (
                    <td key={ref}>{values[ref]?.label ?? "Inconcluso"}</td>
                  ))}
                  <td>{classification(item)}</td>
                  <td>
                    <CaseDetailButton
                      item={item}
                      equivalents={equivalents}
                      onSelect={onSelect}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <nav className="srfl-table-pagination" aria-label="Paginación de casos">
          <ActionButton
            action="previous"
            label="Anterior"
            variant={ButtonVariant.Secondary}
            disabled={tablePage === 0}
            onClick={() => setTablePage((page) => Math.max(0, page - 1))}
          />
          <span>
            Página {tablePage + 1} de {pageCount} · {sorted.length} casos
          </span>
          <ActionButton
            action="next"
            label="Siguiente"
            variant={ButtonVariant.Secondary}
            disabled={tablePage + 1 >= pageCount}
            onClick={() =>
              setTablePage((page) => Math.min(pageCount - 1, page + 1))
            }
          />
        </nav>
      </section>
      {expanded && (
        <Modal
          title="Explorador de la frontera de Pareto"
          className="srfl-chart-modal"
          backdropClassName="srfl-chart-backdrop"
          onClose={() => setExpanded(false)}
        >
          <div className="srfl-expanded-toolbar">
            <div>
              <AxisSelectors
                refs={refs}
                aliases={objectiveAliases}
                x={x}
                y={y}
                changeX={changeX}
                changeY={changeY}
              />
              <ScaleControls
                hasY={refs.length > 1}
                xScale={xScale}
                yScale={yScale}
                xLogK={xLogK}
                yLogK={yLogK}
                setXScale={setXScale}
                setYScale={setYScale}
                setXLogK={setXLogK}
                setYLogK={setYLogK}
              />
            </div>
            <div className="srfl-chart-legend" aria-label="Leyenda">
              <span>
                <i className="is-pareto" /> No dominado
              </span>
              <span>
                <i className="is-dominated" /> Dominado
              </span>
            </div>
          </div>
          <div className="srfl-chart-expanded">{plot(true)}</div>
        </Modal>
      )}
    </section>
  );
}
