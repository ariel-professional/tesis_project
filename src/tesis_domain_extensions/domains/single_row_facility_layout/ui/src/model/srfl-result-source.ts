import type {
  DomainUiHost,
  LayoutCaseResultV2,
  LayoutCaseResultV21,
  SingleRowFacilityLayoutResultV2,
} from "@domain-ui-sdk";

export type FastResultSummaryV21 = {
  schema_version: "2.1.0";
  study_title: string;
  study_description: string | null;
  stations: SingleRowFacilityLayoutResultV2["stations"];
  execution: { domain_run_id: string; domain_experiment_id: string; mode: "high_performance" };
  generation: SingleRowFacilityLayoutResultV2["generation"];
  objective_snapshots: SingleRowFacilityLayoutResultV2["objective_snapshots"];
  designs: Array<{
    design_id: string;
    design_title: string;
    valid_case_count: number | string;
    invalid_combination_count: number | string;
    pareto_case_count: number | string;
    frontier_index: string | null;
    order_indexes: Record<string, string>;
  }>;
  files: Record<string, Record<string, number | string>>;
};

export type SrflCase = LayoutCaseResultV2 | LayoutCaseResultV21;
export type CasePage = {
  items: readonly SrflCase[];
  total: number;
  page: number;
  page_size: 50;
};
export type SrflPlotPoint = {
  case_id: string;
  x: { numerator: number | string; denominator: number | string } | null;
  y: { numerator: number | string; denominator: number | string } | null;
};
export type PlotProjectionGroup = {
  count: number;
  x: number;
  y: number;
  x_min: { numerator: number | string; denominator: number | string };
  x_max: { numerator: number | string; denominator: number | string };
  y_min: { numerator: number | string; denominator: number | string };
  y_max: { numerator: number | string; denominator: number | string };
  case_id?: string;
};
export type FrontierProjectionPoint = { case_id: string; x: number; y: number };
export type ProjectionAxis = {
  objective_id: string;
  scale: "linear" | "square-root" | "adjusted-log" | "percentile";
  minimum: { numerator: number | string; denominator: number | string };
  maximum: { numerator: number | string; denominator: number | string };
  ticks: readonly { position: number; label: string }[];
};
export type PlotProjectionResult = {
  axes: { x: ProjectionAxis; y: ProjectionAxis };
  considered_count: number;
  dominated_count: number;
  level: 0 | 1 | 2;
  section: "groups" | "frontier_positions";
  grid: { columns: number; rows: number };
  total: number;
  items: readonly (PlotProjectionGroup | FrontierProjectionPoint)[];
  next_cursor?: number | null;
};
export type SrflCaseDetail = {
  item: SrflCase;
  equivalents: readonly SrflCase[];
  dominators: readonly (SrflCase & { differences?: Record<string, { numerator: number; denominator: number }> })[];
  equivalent_count?: number;
  loading?: boolean;
};

type OrderDirection = "ascending" | "descending";
type QueryResult<T> = { items?: T[]; next_cursor?: number | null; points?: SrflPlotPoint[] };

function asFraction(value: unknown): { numerator: bigint; denominator: bigint } | null {
  if (typeof value === "object" && value !== null && "numerator" in value && "denominator" in value) {
    const candidate = value as { numerator: number | string; denominator: number | string };
    return { numerator: BigInt(candidate.numerator), denominator: BigInt(candidate.denominator) };
  }
  return null;
}

function objectiveValue(item: SrflCase, objectiveId: string): { numerator: bigint; denominator: bigint } | null {
  const vector = (item as LayoutCaseResultV21).criteria_vector;
  const exact = vector?.[objectiveId];
  if (exact !== undefined) return asFraction(exact);
  if (objectiveId === "retained-compatible-layouts" && item.retained_layouts?.fraction)
    return asFraction(item.retained_layouts.fraction);
  const rel = item.rel_closeness?.find((candidate) => candidate.objective_id === objectiveId);
  if (rel !== undefined) return asFraction(rel.fraction);
  if (item.captured_flow?.objective_id === objectiveId && item.captured_flow.total != null)
    return { numerator: BigInt(item.captured_flow.total), denominator: 1n };
  const adjacency = (item as LayoutCaseResultV2 & { adjacency_values?: Array<{ objective_id: string; total?: number | string | null }> }).adjacency_values;
  const observation = adjacency?.find((candidate) => candidate.objective_id === objectiveId);
  if (observation?.total != null) {
    const text = String(observation.total);
    const [whole, fraction = ""] = text.split(".");
    return { numerator: BigInt(`${whole}${fraction}`), denominator: 10n ** BigInt(fraction.length) };
  }
  return null;
}

function compareExact(left: ReturnType<typeof objectiveValue>, right: ReturnType<typeof objectiveValue>): number {
  if (left === null || right === null) return left === right ? 0 : left === null ? 1 : -1;
  const delta = left.numerator * right.denominator - right.numerator * left.denominator;
  return delta < 0n ? -1 : delta > 0n ? 1 : 0;
}

function compareCases(left: SrflCase, right: SrflCase, order: string): number {
  if (order === "case") return left.case_id.localeCompare(right.case_id);
  if (order === "components") {
    const size = left.component_ids.length - right.component_ids.length;
    return size || left.component_ids.join("\0").localeCompare(right.component_ids.join("\0"));
  }
  if (order.startsWith("criterion:"))
    return compareExact(objectiveValue(left, order.slice("criterion:".length)), objectiveValue(right, order.slice("criterion:".length)));
  return 0;
}

export class SrflResultSource {
  readonly fast: boolean;
  private readonly designs = new Map<string, readonly SrflCase[]>();

  constructor(
    private readonly result: SingleRowFacilityLayoutResultV2 | FastResultSummaryV21,
    private readonly runId: string,
    private readonly host: DomainUiHost,
  ) {
    this.fast = "files" in result;
    if (!this.fast) {
      for (const design of (result as SingleRowFacilityLayoutResultV2).designs)
        this.designs.set(design.design_id, design.cases);
    }
  }

  async casePage(designId: string, order: string, direction: OrderDirection, page: number): Promise<CasePage> {
    if (!Number.isSafeInteger(page) || page < 0) throw new RangeError("La página debe ser un entero no negativo.");
    if (this.fast) {
      if (this.host.getCasePage === undefined) throw new Error("El host no ofrece páginas de casos SRFL.");
      return this.host.getCasePage<CasePage>({ domain_run_id: this.runId, design_id: designId, order, direction, page });
    }
    const all = [...(this.designs.get(designId) ?? [])].sort((left, right) => compareCases(left, right, order) * (direction === "ascending" ? 1 : -1));
    const total = all.length;
    return { items: all.slice(page * 50, page * 50 + 50), total, page, page_size: 50 };
  }

  async caseDetail(designId: string, caseId: string, onProgress?: (detail: SrflCaseDetail) => void): Promise<SrflCaseDetail> {
    if (this.fast) {
      if (this.host.getCaseDetail === undefined || this.host.getDominators === undefined)
        throw new Error("El host no ofrece detalle de casos SRFL.");
      const detail = await this.host.getCaseDetail<{ case: SrflCase; equivalents: SrflCase[]; equivalent_count?: number; next_offset?: number | null }>({ domain_run_id: this.runId, case_id: caseId, equivalent_offset: 0 });
      const equivalents = [...detail.equivalents];
      const dominators: Array<SrflCase & { differences?: Record<string, { numerator: number; denominator: number }> }> = [];
      const publish = () => onProgress?.({ item: detail.case, equivalents: [...equivalents], dominators: [...dominators], equivalent_count: detail.equivalent_count, loading: true });
      publish();
      let offset = detail.next_offset ?? undefined;
      while (offset !== undefined) {
        const page = await this.host.getCaseDetail<{ equivalents: SrflCase[]; next_offset?: number | null }>({ domain_run_id: this.runId, case_id: caseId, equivalent_offset: offset });
        equivalents.push(...page.equivalents);
        publish();
        offset = page.next_offset ?? undefined;
      }
      let cursor: number | undefined = 0;
      while (cursor !== undefined) {
        const response: QueryResult<SrflCase & { differences?: Record<string, { numerator: number; denominator: number }> }> = await this.host.getDominators({ domain_run_id: this.runId, case_id: caseId, cursor });
        dominators.push(...(response.items ?? []));
        publish();
        cursor = response.next_cursor ?? undefined;
      }
      const completed = { item: detail.case, equivalents, dominators, equivalent_count: detail.equivalent_count, loading: false };
      onProgress?.(completed);
      return completed;
    }
    const cases = this.designs.get(designId) ?? [];
    const item = cases.find((candidate) => candidate.case_id === caseId);
    if (item === undefined) throw new Error("El caso no existe en el resultado.");
    const equivalents = cases.filter((candidate) => candidate.forest_id === item.forest_id);
    const dominatedIds = item.pareto_classification.dominated_by_case_ids ?? [];
    const dominators = dominatedIds.flatMap((id) => {
      const preferred = cases.find((candidate) => candidate.case_id === id);
      return preferred === undefined ? [] : [preferred];
    });
    return { item, equivalents, dominators };
  }

  async frontier(designId: string): Promise<readonly SrflCase[]> {
    if (!this.fast) return (this.designs.get(designId) ?? []).filter((item) => item.pareto_classification.pareto_optimal === true);
    if (this.host.getFrontier === undefined) throw new Error("El host no ofrece la frontera SRFL.");
    const all: SrflCase[] = [];
    let cursor: number | undefined = 0;
    while (cursor !== undefined) {
      const response: QueryResult<SrflCase> = await this.host.getFrontier({ domain_run_id: this.runId, design_id: designId, cursor });
      all.push(...(response.items ?? []));
      cursor = response.next_cursor ?? undefined;
    }
    return all;
  }

  async plotPoints(designId: string, xObjectiveId: string, yObjectiveId: string): Promise<readonly SrflPlotPoint[]> {
    if (!this.fast) {
      return (this.designs.get(designId) ?? []).map((item) => ({
        case_id: item.case_id,
        x: objectiveValue(item, xObjectiveId) === null ? null : { numerator: String(objectiveValue(item, xObjectiveId)!.numerator), denominator: String(objectiveValue(item, xObjectiveId)!.denominator) },
        y: objectiveValue(item, yObjectiveId) === null ? null : { numerator: String(objectiveValue(item, yObjectiveId)!.numerator), denominator: String(objectiveValue(item, yObjectiveId)!.denominator) },
      }));
    }
    if (this.host.getPlotPoints === undefined) throw new Error("El host no ofrece puntos SRFL.");
    const all: SrflPlotPoint[] = [];
    let cursor: number | undefined = 0;
    while (cursor !== undefined) {
      const response: QueryResult<SrflPlotPoint> = await this.host.getPlotPoints({ domain_run_id: this.runId, design_id: designId, x_objective_id: xObjectiveId, y_objective_id: yObjectiveId, cursor });
      all.push(...(response.points ?? []));
      cursor = response.next_cursor ?? undefined;
    }
    return all;
  }

  async plotProjection(params: {
    design_id: string;
    x_objective_id: string;
    y_objective_id: string;
    x_scale: "automatic" | "linear" | "square-root" | "adjusted-log" | "percentile";
    y_scale: "automatic" | "linear" | "square-root" | "adjusted-log" | "percentile";
    x_log_k: number;
    y_log_k: number;
    level: 0 | 1 | 2;
    section: "groups" | "frontier_positions";
  }): Promise<PlotProjectionResult> {
    if (!this.fast || this.host.getPlotProjection === undefined)
      throw new Error("El host no ofrece proyecciones agrupadas SRFL.");
    const items: PlotProjectionResult["items"][number][] = [];
    let cursor: number | undefined = 0;
    let first: PlotProjectionResult | null = null;
    while (cursor !== undefined) {
      const page: PlotProjectionResult = await this.host.getPlotProjection<PlotProjectionResult>({
        domain_run_id: this.runId,
        ...params,
        cursor,
      });
      first ??= page;
      items.push(...page.items);
      cursor = page.next_cursor ?? undefined;
    }
    if (first === null) throw new Error("El gateway devolvió una proyección vacía.");
    return { ...first, items };
  }
}

export function createSrflResultSource(
  result: SingleRowFacilityLayoutResultV2 | FastResultSummaryV21,
  runId: string,
  host: DomainUiHost,
): SrflResultSource {
  return new SrflResultSource(result, runId, host);
}
