import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type {
  AttachmentService,
  DomainUiHost,
  LayoutCaseResultV2,
  SingleRowFacilityLayoutDraftV2,
  SingleRowFacilityLayoutResult,
  SingleRowFacilityLayoutResultV2,
} from "@domain-ui-sdk";
import { DesignComparison, IndexedParetoChart } from "@srfl-ui/components/results/DesignComparison";
import { ResultSummary } from "@srfl-ui/components/results/ResultSummary";
import { MetricsView } from "@srfl-ui/components/results/MetricsView";
import { CaseDetail } from "@srfl-ui/components/results/CaseDetail";
import type { FastResultSummaryV21, PlotProjectionResult, SrflResultSource } from "@srfl-ui/model/srfl-result-source";
afterEach(() => document.body.replaceChildren());

const caseResult = (id: string): LayoutCaseResultV2 => ({
  case_id: id,
  core_run_id: "core-reference",
  design_id: "d1",
  component_ids: ["c1"],
  mandatory_component_ids: ["c1"],
  added_component_ids: [],
  compatible_layout_count: {
    value: 12,
    exact_value: 12,
    reference_value: 12,
    comparison_status: "match",
    counting_convention: "undirected_paths_reverse_identified",
    method: null,
  },
  forest_id: `forest-${id}`,
  forest_structure: { paths: [["a", "b"]], isolated_station_ids: [] },
  edges: [["a", "b"]],
  prescribed_edge_count: 1,
  feasibility: "feasible",
  diagnostics: [],
  limitations: [],
  technical_metrics: null,
  retained_layouts: {
    objective_id: "retained-compatible-layouts",
    objective_version: "1",
    direction: "maximize",
    unit: "fracción exacta",
    status: "conclusive",
    compatible_layout_count: 12,
    base_layout_count: 12,
    fraction: { numerator: 1, denominator: 1 },
  },
  rel_closeness: [],
  findings: [],
  pareto_classification: {
    status: "conclusive",
    pareto_optimal: true,
    dominated: false,
    objective_refs: ["retained-compatible-layouts"],
  },
});
const result: SingleRowFacilityLayoutResultV2 = {
  schema_version: "2.0.0",
  domain: { id: "single-row-facility-layout", version: "2.0.0" },
  execution: {
    domain_run_id: "run-reference",
    domain_experiment_id: "a".repeat(64),
    status: "completed",
  },
  study_title: "Hospital",
  study_description: null,
  study_id: "hospital",
  stations: [
    { id: "a", name: "A" },
    { id: "b", name: "B" },
  ],
  objective_snapshots: [
    {
      definition: {
        id: "retained-compatible-layouts",
        version: "1",
        name: "Flexibilidad de distribución conservada",
        summary: "Resumen histórico",
        decision_question: "Pregunta histórica",
        classification: "criterion",
        direction: "maximize",
        unit: "fracción exacta",
        formula: "H_i / H_D",
        scope: "case",
        required_inputs: ["core-layout-count"],
        evidence: ["Evidencia histórica"],
        limitations: ["Limitación histórica"],
      },
    },
  ],
  limitations: [],
  generation: {
    theoretical_combinations: 1,
    valid_selections: 1,
    invalid_combinations: 0,
    structural_invalid_combinations: 0,
    forbidden_combinations: 0,
    core_cases: 1,
    cycle_pruned_branches: 0,
    degree_pruned_branches: 0,
    duplicate_forests: 0,
  },
  designs: [
    {
      design_id: "d1",
      design_title: "Diseño 1",
      valid_case_count: 1,
      invalid_combination_count: 0,
      invalid_combination_summaries: [],
      pareto_case_ids: ["case-reference"],
      candidate_component_ids: [],
      mandatory_component_ids: ["c1"],
      theoretical_combinations: 1,
      base_case_id: "case-reference",
      base_layout_count: null,
      cases: [caseResult("case-reference")],
    },
  ],
};

test.each(["maximize", "minimize"] as const)("negative Pareto differences keep their sign and %s direction in the case detail", (direction) => {
  const item = caseResult("negative");
  const preferred = direction === "maximize" ? "-0.0000001" : "-0.0000002";
  const other = direction === "maximize" ? "-0.0000002" : "-0.0000001";
  item.pareto_classification = {
    status: "conclusive", pareto_optimal: false, dominated: true,
    objective_refs: ["adjacency-cost"], dominated_by_case_ids: ["preferred"],
    differences: [{ objective_id: "adjacency-cost", preferred_case_id: "preferred", other_case_id: item.case_id,
                    preferred_value: preferred, other_value: other }],
  };
  render(<CaseDetail item={item} stations={result.stations} onClose={() => undefined}
    objectiveAliases={{ "adjacency-cost": "Costo" }} objectiveDirections={{ "adjacency-cost": direction }} />);
  expect(screen.getByText(preferred)).toBeTruthy();
  expect(screen.getByText(other)).toBeTruthy();
  expect(screen.getByText(direction === "maximize" ? "Aumenta en un 50 %" : "Disminuye en un 100 %")).toBeTruthy();
});

test("results show typed v2 criteria and case detail without utility", async () => {
  render(<ResultSummary result={result} host={{} as DomainUiHost} onHome={() => undefined} />);
  expect(
    screen.getByRole("region", { name: "Explorador Pareto" }),
  ).toBeTruthy();
  expect(screen.queryByText(/Utilidad/)).toBeNull();
  expect(screen.getAllByText(/Flexibilidad de distribución/).length).toBeGreaterThan(0);
  expect(screen.queryByText(/Flexibilidad de distribución conservada/)).toBeNull();
  fireEvent.click(
    within(
      screen.getByRole("region", { name: "Todos los casos válidos" }),
    ).getByRole("button", { name: "Ver detalle" }),
  );
  expect(await screen.findByRole("dialog", { name: "Detalle del caso" })).toBeTruthy();
  expect(screen.getByText("Disponibilidad")).toBeTruthy();
});
test("v2 results load immutable documentation and expose metadata from a selected edge", async () => {
  const documentation = {
    schema_version: "2.0.0",
    domain: { id: "single-row-facility-layout", version: "2.0.0" },
    study: {
      id: "hospital", title: "Hospital", stations: result.stations,
      components: [{ id: "c1", station_ids: ["a", "b"], description: "Conexión operativa", attachments: [] }],
      designs: [{ id: "d1", title: "Diseño 1", base_component_ids: ["c1"], description: "Antecedente del diseño", attachments: [] }],
    },
    decision_model: {
      selected_objectives: [{ id: "rel-closeness", version: "1" }],
      rel_closeness: { requirements: [{ first_station_id: "a", second_station_id: "b", level: "A", reason: "Traslado frecuente", provenance: "Relevamiento 2026" }] },
      adjacency_flow: [{ id: "costo", name: "Costo operativo", description: "Costo del vínculo", direction: "minimize", unit: "ARS", reference_period: "mes", provenance: "Contabilidad", directed: false, entries: [{ from_station_id: "a", to_station_id: "b", value: "125" }] }],
      undesired_prescribed_adjacencies: [],
    },
    execution: {}, reporting: { invalid_combinations: "summary" },
  } as unknown as SingleRowFacilityLayoutDraftV2;
  const service = {
    documentation: async () => documentation,
    stage: async () => { throw new Error("not used"); },
    readRange: async () => new Uint8Array(),
    openLink: async () => undefined,
    discardStaged: async () => undefined,
  } as AttachmentService;
  render(<ResultSummary result={result} service={service} onHome={() => undefined} />);
  await screen.findByText("Antecedente del diseño");
  fireEvent.click(within(screen.getByRole("region", { name: "Todos los casos válidos" })).getByRole("button", { name: "Ver detalle" }));
  fireEvent.click(await screen.findByRole("button", { name: "Ver detalle de A y B" }));
  expect(screen.getByText("Traslado frecuente")).toBeTruthy();
  expect(screen.getByText("Relevamiento 2026")).toBeTruthy();
  expect(screen.getByText("Costo operativo")).toBeTruthy();
  expect(screen.getByText(/125 ARS\/mes/)).toBeTruthy();
  expect(screen.getAllByText("Conexión operativa").length).toBeGreaterThan(0);
});

test("2.1 fast results request a bounded indexed page and expose global paging", async () => {
  const fast = {
    schema_version: "2.1.0", study_title: "Hospital rápido", study_description: null,
    stations: result.stations, execution: { domain_run_id: "run-fast", domain_experiment_id: "b".repeat(64), mode: "high_performance" },
    generation: result.generation, objective_snapshots: [
      { id: "adjacency-m1", name: "Matriz 1", direction: "maximize" },
      { id: "adjacency-m2", name: "Matriz 2", direction: "minimize" },
    ].map(({ id, name, direction }) => ({ definition: { id, version: "1", name, summary: name, decision_question: name, classification: "criterion", direction, unit: "exact", formula: name, scope: "case", required_inputs: ["input"], evidence: ["test"], limitations: ["test"] } })),
    designs: [{ design_id: "d1", design_title: "Diseño 1", valid_case_count: 120, invalid_combination_count: 0, pareto_case_count: 1, frontier_index: "frontier/design-0.u64", order_indexes: { case: "orders/design-0-case.u64" } }],
    limitations: [], files: {},
  } as unknown as FastResultSummaryV21;
  const matrixCase = {
    ...caseResult("point-1"),
    criteria_vector: { "adjacency-m1": { numerator: 5, denominator: 2 }, "adjacency-m2": { numerator: -5, denominator: 4 } },
    adjacency_values: [
      { objective_id: "adjacency-m1", status: "conclusive", total: "2.50", unit: "kg", reference_period: null },
      { objective_id: "adjacency-m2", status: "conclusive", total: "-1.25", unit: "ARS", reference_period: "mes" },
    ],
  };
  const getCasePage = vi.fn(async () => ({ items: [matrixCase], total: 120, page: 0, page_size: 50 as const }));
  const getCaseDetail = vi.fn(async () => ({ case: matrixCase, equivalents: [matrixCase], equivalent_count: 1, next_offset: null }));
  const getPlotPoints = vi.fn(async () => ({ points: [{ case_id: "point-1", x: { numerator: "5", denominator: "2" }, y: { numerator: "-5", denominator: "4" } }], next_cursor: null }));
  const getPlotProjection = vi.fn(async (params: { section: string }) => ({
    axes: {
      x: { objective_id: "adjacency-m1", scale: "linear" as const, minimum: { numerator: -5, denominator: 4 }, maximum: { numerator: 5, denominator: 2 }, ticks: [0, 0.2, 0.4, 0.6, 0.8, 1].map((position) => ({ position, label: String(position) })) },
      y: { objective_id: "adjacency-m2", scale: "linear" as const, minimum: { numerator: -5, denominator: 4 }, maximum: { numerator: 5, denominator: 2 }, ticks: [0, 0.2, 0.4, 0.6, 0.8, 1].map((position) => ({ position, label: String(position) })) },
    },
    considered_count: 120,
    dominated_count: 119,
    level: 0 as const,
    section: params.section as "groups" | "frontier_positions",
    total: params.section === "frontier_positions" ? 1 : 1,
    items: params.section === "frontier_positions"
      ? [{ case_id: "point-1", x: 0.5, y: 0.5 }]
      : [{ count: 119, x: 0.5, y: 0.5, x_min: { numerator: 0, denominator: 1 }, x_max: { numerator: 5, denominator: 2 }, y_min: { numerator: -5, denominator: 4 }, y_max: { numerator: 2, denominator: 1 } }],
    next_cursor: null,
  }));
  const host = {
    getCasePage,
    getFrontier: async () => ({ items: [matrixCase], next_cursor: null }),
    getPlotPoints,
    getPlotProjection,
    getCaseDetail,
    getDominators: async () => ({ items: [], next_cursor: null }),
  } as unknown as DomainUiHost;
  const { unmount } = render(<ResultSummary result={fast} host={host} onHome={() => undefined} />);
  expect(screen.getByRole("navigation", { name: "Índice de Detalle" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Tabla completa" })).toBeTruthy();
  expect(screen.getByText("Criterios aplicados")).toBeTruthy();
  expect(await screen.findByText("120 casos · página 1")).toBeTruthy();
  const casesTable = screen.getByRole("region", { name: "Todos los casos válidos" });
  expect(within(casesTable).getByText("2,50 kg")).toBeTruthy();
  expect(within(casesTable).getByText("-1,25 ARS/mes")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Siguiente" }).hasAttribute("disabled")).toBe(false);
  expect(getCasePage).toHaveBeenCalledWith({ domain_run_id: "run-fast", design_id: "d1", order: "case", direction: "ascending", page: 0 });
  const detailButton = within(screen.getByRole("region", { name: "Todos los casos válidos" })).getByRole("button", { name: "Ver detalle" });
  expect(detailButton.textContent).toBe("");
  fireEvent.click(detailButton);
  expect(await screen.findByRole("dialog", { name: "Detalle del caso" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
  const plotted = await screen.findByRole("button", { name: /point-1: No dominado/ });
  fireEvent.click(plotted);
  expect(await screen.findByRole("dialog", { name: "Detalle del caso" })).toBeTruthy();
  expect(getCaseDetail).toHaveBeenCalledWith({ domain_run_id: "run-fast", case_id: "point-1", equivalent_offset: 0 });
  const chart = screen.getAllByRole("region", { name: "Gráfico de la frontera de Pareto" }).at(-1)!;
  expect(chart.querySelectorAll(".srfl-point-group")).toHaveLength(0);
  expect(within(chart).queryByRole("button", { name: "Mostrar más detalle" })).toBeNull();
  expect(within(chart).getByRole("checkbox", { name: "Reducir el ruido visual" })).toBeTruthy();
  expect(getPlotPoints).toHaveBeenCalled();
  expect(getPlotProjection).not.toHaveBeenCalled();
  const exactRequests = getPlotPoints.mock.calls.length;
  fireEvent.change(within(chart).getByRole("combobox", { name: "Transformación X" }), { target: { value: "square-root" } });
  expect(getPlotPoints.mock.calls).toHaveLength(exactRequests);

  unmount();
  const atLimit = render(<ResultSummary result={{ ...fast, designs: [{ ...fast.designs[0]!, valid_case_count: 10000 }] }} host={host} onHome={() => undefined} />);
  const limitChart = screen.getAllByRole("region", { name: "Gráfico de la frontera de Pareto" }).at(-1)!;
  expect(within(limitChart).queryByRole("checkbox", { name: "Reducir el ruido visual" })).toBeNull();
  expect(getPlotProjection).not.toHaveBeenCalled();

  atLimit.unmount();
  render(<ResultSummary result={{ ...fast, designs: [{ ...fast.designs[0]!, valid_case_count: 10001 }] }} host={host} onHome={() => undefined} />);
  const largeChart = screen.getAllByRole("region", { name: "Gráfico de la frontera de Pareto" }).at(-1)!;
  expect(within(largeChart).queryByRole("checkbox", { name: "Reducir el ruido visual" })).toBeNull();
  expect(await within(largeChart).findByText("Nivel 0 · 16 × 8")).toBeTruthy();
  expect(largeChart.querySelectorAll(".srfl-point-group")).toHaveLength(1);
  fireEvent.click(within(largeChart).getByRole("button", { name: "Mostrar más detalle" }));
  expect(await within(largeChart).findByText("Nivel 1 · 32 × 16")).toBeTruthy();
  expect(getPlotProjection).toHaveBeenCalledWith(expect.objectContaining({ level: 1, section: "groups" }));
});

test.each([1, 1_000_000])("visual noise reduction retains the nearest real case and the whole frontier at scale %i", async (multiplier) => {
  const frontierCase = caseResult("frontier");
  frontierCase.retained_layouts!.fraction = { numerator: 0, denominator: 1 };
  const values = [
    ["case-a", 475],
    ["case-b", 490],
    ["case-c", 495],
    ["case-far", 1000],
  ] as const;
  render(<IndexedParetoChart
    objectives={[{ id: "retained-compatible-layouts", label: "Flexibilidad" }]}
    frontierCases={[frontierCase]}
    loadPoints={async () => [
      { case_id: "frontier", x: { numerator: "0", denominator: "1" }, y: null },
      ...values.map(([caseId, value]) => ({ case_id: caseId, x: { numerator: String(value * multiplier), denominator: "1" }, y: null })),
    ]}
    visualNoiseReductionAvailable
    onSelectCaseId={() => undefined}
  />);
  const chart = screen.getByRole("region", { name: "Gráfico de la frontera de Pareto" });
  await within(chart).findByRole("button", { name: /case-a: Dominado/ });
  fireEvent.change(within(chart).getByRole("combobox", { name: "Transformación X" }), { target: { value: "linear" } });
  fireEvent.click(within(chart).getByRole("checkbox", { name: "Reducir el ruido visual" }));
  expect(within(chart).getByRole("combobox", { name: "Nivel de reducción" })).toBeTruthy();
  expect(within(chart).getByRole("button", { name: /frontier: No dominado/ })).toBeTruthy();
  expect(within(chart).getByRole("button", { name: /case-b: Dominado/ })).toBeTruthy();
  expect(within(chart).queryByRole("button", { name: /case-a: Dominado/ })).toBeNull();
  expect(within(chart).queryByRole("button", { name: /case-c: Dominado/ })).toBeNull();
  expect(within(chart).getByRole("button", { name: /case-far: Dominado/ })).toBeTruthy();
  expect(within(chart).getByText("Mostrando 3 de 5 puntos proyectables. La frontera permanece completa.")).toBeTruthy();
  fireEvent.click(within(chart).getByRole("button", { name: "Ampliar gráfico" }));
  const expanded = screen.getByRole("dialog", { name: "Explorador de la frontera de Pareto" });
  expect(within(expanded).getByRole("checkbox", { name: "Reducir el ruido visual" })).toBeTruthy();
  expect(within(expanded).getByText("Mostrando 4 de 5 puntos proyectables. La frontera permanece completa.")).toBeTruthy();
  fireEvent.click(within(expanded).getByRole("button", { name: "Cerrar" }));
  fireEvent.change(within(chart).getByRole("combobox", { name: "Nivel de reducción" }), { target: { value: "low" } });
  expect(within(chart).getByText("Mostrando 4 de 5 puntos proyectables. La frontera permanece completa.")).toBeTruthy();
  fireEvent.click(within(chart).getByRole("checkbox", { name: "Reducir el ruido visual" }));
  expect(within(chart).queryByRole("combobox", { name: "Nivel de reducción" })).toBeNull();
  expect(within(chart).getByRole("button", { name: /case-a: Dominado/ })).toBeTruthy();
  expect(within(chart).getByRole("button", { name: /case-c: Dominado/ })).toBeTruthy();
});
test("indexed Pareto chart renders a single selected objective", async () => {
  render(<IndexedParetoChart
    objectives={[{ id: "single-criterion", label: "Criterio" }]}
    frontierCases={[caseResult("single-point")]}
    loadPoints={async () => [{ case_id: "single-point", x: { numerator: "3", denominator: "2" }, y: null }]}
    onSelectCaseId={() => undefined}
  />);
  expect(await screen.findByRole("img", { name: "Eje Criterio" })).toBeTruthy();
});

test("SRFL 2.x switches between sibling result tabs and renders titled metric cards", async () => {
  const getResultMetrics = vi.fn(async () => ({
    metric_id: "base-flexibility",
    summary: { denominator: "1" },
    status: "inconclusive",
    total: 0,
    rows: [],
    next_cursor: null,
  }));
  const host = { getResultMetrics } as unknown as DomainUiHost;
  render(<ResultSummary result={result} host={host} onHome={() => undefined} />);
  expect(screen.getByRole("tab", { name: "Detalle" }).getAttribute("aria-selected")).toBe("true");
  fireEvent.keyDown(screen.getByRole("tablist", { name: "Vistas del resultado" }), { key: "ArrowRight" });
  expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Métricas" }));
  const panel = screen.getByRole("tabpanel", { name: "Métricas" });
  for (const title of [
    "Flexibilidad conservada frente a la base",
    "Extremos por criterio",
    "Presencia en Pareto",
    "Componentes que aparecen juntos",
    "Superposición estructural",
    "Adyacencias decisivas para un criterio",
    "Advertencias en alternativas no dominadas",
    "Capacidad de discriminación de cada criterio",
    "Cambios respecto de la base",
    "Patrones compartidos entre diseños",
    "Alternativa no dominada más cercana",
    "Conflicto entre criterios",
    "Sensibilidad de Pareto a un criterio",
  ]) {
    expect(within(panel).getByRole("heading", { name: title })).toBeTruthy();
  }
  expect((await screen.findAllByText("Este análisis no es concluyente con los resultados disponibles.")).length).toBeGreaterThan(0);
  expect(screen.getByRole("navigation", { name: "Índice de Métricas" })).toBeTruthy();
  expect(getResultMetrics).toHaveBeenCalled();
  expect(
    getResultMetrics,
  ).not.toHaveBeenCalledWith(expect.objectContaining({ metric_id: "pareto-sensitivity" }));
  expect(screen.getByRole("tab", { name: "Métricas" }).getAttribute("aria-selected")).toBe("true");
  fireEvent.click(screen.getByRole("tab", { name: "Detalle" }));
  expect(screen.getByRole("tab", { name: "Detalle" }).getAttribute("aria-selected")).toBe("true");
});

test("Pareto presence hides simple components and opens every matching frontier case", async () => {
  const frontier = [
    { ...caseResult("first"), edges: [["a", "b"], ["b", "c"]] as [string, string][], added_component_ids: ["simple-a", "long-a"], captured_flow: { objective_id: "captured-adjacency-flow", status: "conclusive", total: 125, unit: "préstamos", horizon: "mes" } },
    { ...caseResult("second"), edges: [["a", "b"]] as [string, string][], added_component_ids: ["simple-a"] },
    { ...caseResult("third"), edges: [["c", "d"]] as [string, string][], added_component_ids: ["simple-c", "long-b"] },
  ];
  const source = { frontier: async () => frontier } as unknown as SrflResultSource;
  const onOpenCase = vi.fn(async (_caseId: string) => undefined);
  const getResultMetrics = vi.fn(async ({ metric_id }: { metric_id: string }) => metric_id === "pareto-presence" ? {
    status: "conclusive", total: 8, next_cursor: null, summary: {},
    rows: [
      { kind: "adjacency", id: "a–b", count: 2, denominator: 3 },
      { kind: "adjacency", id: "b–c", count: 1, denominator: 3 },
      { kind: "adjacency", id: "c–d", count: 1, denominator: 3 },
      { kind: "component", id: "simple-a", count: 2, denominator: 3 },
      { kind: "component", id: "simple-b", count: 0, denominator: 3 },
      { kind: "component", id: "simple-c", count: 1, denominator: 3 },
      { kind: "component", id: "long-a", count: 1, denominator: 3 },
      { kind: "component", id: "long-b", count: 1, denominator: 3 },
    ],
  } : { status: "inconclusive", total: 0, rows: [], next_cursor: null, summary: {} });
  render(<MetricsView host={{ getResultMetrics } as unknown as DomainUiHost} source={source} runId="run-reference" designId="d1" objectives={[
    { definition: { id: "retained-compatible-layouts", name: "Flexibilidad de distribución", unit: "fracción exacta" } },
    { definition: { id: "captured-adjacency-flow", name: "Volumen de co-préstamos", unit: "préstamos/mes" } },
  ]} designTitles={[]} components={[
    { id: "simple-a", station_ids: ["a", "b"] },
    { id: "simple-b", station_ids: ["b", "c"] },
    { id: "simple-c", station_ids: ["c", "d"] },
    { id: "long-a", station_ids: ["a", "b", "c"] },
    { id: "long-b", station_ids: ["b", "c", "d"] },
  ]} onOpenCase={onOpenCase} />);
  const card = await screen.findByRole("article", { name: "Presencia en Pareto" });
  expect(within(card).getByRole("heading", { name: "Adyacencias opcionales" })).toBeTruthy();
  expect(within(card).getByRole("heading", { name: "Componentes opcionales" })).toBeTruthy();
  expect(within(card).queryByText("simple-a")).toBeNull();
  expect(within(card).queryByText("simple-b")).toBeNull();
  expect(within(card).queryByText("simple-c")).toBeNull();
  expect(within(card).getByText("long-a")).toBeTruthy();
  expect(within(card).getByText("long-b")).toBeTruthy();
  const adjacency = within(card).getByRole("row", { name: /a–b/ });
  fireEvent.click(within(adjacency).getByRole("button", { name: "Ver casos de a–b" }));
  const modal = screen.getByRole("dialog", { name: "Casos con la adyacencia a–b" });
  expect(within(modal).getByRole("columnheader", { name: "Flexibilidad de distribución" })).toBeTruthy();
  expect(within(modal).getByRole("columnheader", { name: "Volumen de co-préstamos" })).toBeTruthy();
  expect(within(modal).getAllByRole("row")).toHaveLength(3);
  const firstCase = within(modal).getByRole("row", { name: /Alternativa 1/ });
  expect(within(firstCase).getByText("100,00 %")).toBeTruthy();
  expect(within(firstCase).getByText("125 préstamos/mes")).toBeTruthy();
  fireEvent.click(within(firstCase).getByRole("button", { name: /Ver detalle de Alternativa 1/ }));
  expect(onOpenCase).toHaveBeenCalledWith("first");
  fireEvent.click(within(modal).getByRole("button", { name: "Cerrar" }));
  expect(screen.queryByRole("dialog", { name: "Casos con la adyacencia a–b" })).toBeNull();
  fireEvent.click(within(within(card).getByRole("row", { name: /long-a/ })).getByRole("button", { name: "Ver casos de long-a" }));
  expect(within(screen.getByRole("dialog", { name: "Casos con el componente long-a" })).getAllByRole("row")).toHaveLength(2);
});

test("Pareto presence omits the component section when every component is one adjacency", async () => {
  const getResultMetrics = vi.fn(async ({ metric_id }: { metric_id: string }) => metric_id === "pareto-presence" ? {
    status: "conclusive", total: 2, next_cursor: null, summary: {},
    rows: [
      { kind: "adjacency", id: "a–b", count: 1, denominator: 1 },
      { kind: "component", id: "simple-a", count: 1, denominator: 1 },
    ],
  } : { status: "inconclusive", total: 0, rows: [], next_cursor: null, summary: {} });
  render(<MetricsView host={{ getResultMetrics } as unknown as DomainUiHost} source={{ frontier: async () => [{ ...caseResult("only"), added_component_ids: ["simple-a"] }] } as unknown as SrflResultSource} runId="run-reference" designId="d1" objectives={[]} designTitles={[]} components={[{ id: "simple-a", station_ids: ["a", "b"] }]} />);
  const card = await screen.findByRole("article", { name: "Presencia en Pareto" });
  expect(await within(card).findByText("a–b")).toBeTruthy();
  expect(within(card).queryByRole("heading", { name: "Componentes opcionales" })).toBeNull();
});

test("cooccurring components open the matching frontier cases and their details", async () => {
  const source = { frontier: async () => [
    { ...caseResult("first"), added_component_ids: ["c1", "c2"] },
    { ...caseResult("second"), added_component_ids: ["c1", "c2", "c3"] },
    { ...caseResult("third"), component_ids: ["c1", "c2"], added_component_ids: ["c1"] },
  ] } as unknown as SrflResultSource;
  const onOpenCase = vi.fn(async (_caseId: string) => undefined);
  const getResultMetrics = vi.fn(async ({ metric_id }: { metric_id: string }) => metric_id === "component-cooccurrence" ? {
    status: "conclusive", total: 1, next_cursor: null, summary: {},
    rows: [{ components: ["c1", "c2"], together: 2, first_alone: 3, second_alone: 2, denominator: 3 }],
  } : { status: "inconclusive", total: 0, rows: [], next_cursor: null, summary: {} });
  render(<MetricsView host={{ getResultMetrics } as unknown as DomainUiHost} source={source} runId="run-reference" designId="d1" objectives={[
    { definition: { id: "retained-compatible-layouts", name: "Flexibilidad de distribución", unit: "fracción exacta" } },
  ]} designTitles={[]} onOpenCase={onOpenCase} />);
  const card = await screen.findByRole("article", { name: "Componentes que aparecen juntos" });
  fireEvent.click(await within(card).findByRole("button", { name: "Ver casos con c1 y c2" }));
  const modal = screen.getByRole("dialog", { name: "Casos con c1 y c2" });
  expect(within(modal).getByText("2 casos de la frontera")).toBeTruthy();
  expect(within(modal).getAllByRole("row")).toHaveLength(3);
  expect(within(modal).queryByText(/Alternativa 3/)).toBeNull();
  const firstCase = within(modal).getByRole("row", { name: /Alternativa 1/ });
  expect(within(firstCase).getByText("100,00 %")).toBeTruthy();
  fireEvent.click(within(firstCase).getByRole("button", { name: /Ver detalle de Alternativa 1/ }));
  expect(onOpenCase).toHaveBeenCalledWith("first");
});
test("criterion contributions show each case total, signed share, and case detail", async () => {
  const source = { frontier: async () => [
    { ...caseResult("positive"), captured_flow: { objective_id: "captured-adjacency-flow", status: "conclusive", total: 80, unit: "préstamos", horizon: "mes", contributions: [
      { first_station_id: "c", second_station_id: "d", total: 10 },
      { first_station_id: "a", second_station_id: "b", total: 100 },
      { first_station_id: "d", second_station_id: "e", total: -5 },
      { first_station_id: "b", second_station_id: "c", total: -25 },
    ] }, adjacency_values: [{ objective_id: "adjacency-cost", status: "conclusive", total: "-20", unit: "ARS", reference_period: "mes", contributions: [
      { first_station_id: "d", second_station_id: "e", total: "5" },
      { first_station_id: "e", second_station_id: "f", total: "-25" },
    ] }] },
    { ...caseResult("zero"), captured_flow: { objective_id: "captured-adjacency-flow", status: "conclusive", total: 0, unit: "préstamos", horizon: "mes", contributions: [
      { first_station_id: "f", second_station_id: "g", total: 5 },
      { first_station_id: "g", second_station_id: "h", total: -5 },
    ] } },
  ] } as unknown as SrflResultSource;
  const onOpenCase = vi.fn(async (_caseId: string) => undefined);
  const getResultMetrics = vi.fn(async ({ metric_id, criterion_id }: { metric_id: string; criterion_id?: string }) => metric_id === "criterion-contributions" && criterion_id === "adjacency-cost" ? {
    status: "conclusive", total: 1, next_cursor: null, summary: {},
    rows: [{ case_id: "positive", criterion_id: "adjacency-cost", adjacency: "d–e", contribution: "5", unit: "ARS", period: "mes" }],
  } : metric_id === "criterion-contributions" ? {
    status: "conclusive", total: 3, next_cursor: null, summary: {},
    rows: [
      { case_id: "positive", criterion_id: "captured-adjacency-flow", adjacency: "a–b", contribution: "40", unit: "préstamos", period: "mes" },
      { case_id: "positive", criterion_id: "captured-adjacency-flow", adjacency: "b–c", contribution: "-5", unit: "préstamos", period: "mes" },
      { case_id: "zero", criterion_id: "captured-adjacency-flow", adjacency: "c–d", contribution: "5", unit: "préstamos", period: "mes" },
    ],
  } : { status: "inconclusive", total: 0, rows: [], next_cursor: null, summary: {} });
  render(<MetricsView host={{ getResultMetrics } as unknown as DomainUiHost} source={source} runId="run-reference" designId="d1" objectives={[
    { definition: { id: "captured-adjacency-flow", name: "Volumen de co-préstamos", unit: "préstamos/mes" } },
    { definition: { id: "adjacency-cost", name: "Costo", unit: "ARS/mes" } },
  ]} designTitles={[]} onOpenCase={onOpenCase} />);
  const card = await screen.findByRole("article", { name: "Adyacencias decisivas para un criterio" });
  fireEvent.change(within(card).getByRole("combobox", { name: "Criterio cuyos aportes querés ver" }), { target: { value: "captured-adjacency-flow" } });
  const positive = await within(card).findByRole("row", { name: /Alternativa 1/ });
  expect(within(card).getAllByRole("row")).toHaveLength(3);
  expect(within(positive).getByText("80 préstamos por mes")).toBeTruthy();
  expect(within(positive).getByText("125,00 %")).toBeTruthy();
  expect(within(positive).getByText("−31,25 %")).toBeTruthy();
  expect(within(positive).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
    expect.stringContaining("a–b"),
    expect.stringContaining("b–c"),
    expect.stringContaining("c–d"),
  ]);
  expect(within(positive).queryByText("d–e")).toBeNull();
  expect(within(positive).getByText("+1 adyacencias más en el detalle")).toBeTruthy();
  expect(within(within(card).getByRole("row", { name: /Alternativa 2/ })).getAllByText("No aplica (total cero)")).toHaveLength(2);
  fireEvent.click(within(positive).getByRole("button", { name: /Ver detalle de Alternativa 1/ }));
  expect(onOpenCase).toHaveBeenCalledWith("positive");
  fireEvent.change(within(card).getByRole("combobox", { name: "Criterio cuyos aportes querés ver" }), { target: { value: "adjacency-cost" } });
  const cost = await within(card).findByRole("row", { name: /Alternativa 1/ });
  expect(within(card).getAllByRole("row")).toHaveLength(2);
  expect(within(cost).getByText("-20 ARS por mes")).toBeTruthy();
  expect(within(cost).getByText("125,00 %")).toBeTruthy();
  expect(within(cost).getByText("−25,00 %")).toBeTruthy();
});
test("criterion contributions paginate complete alternatives independently of metric rows", async () => {
  const source = { frontier: async () => Array.from({ length: 51 }, (_, index) => ({
    ...caseResult(`case-${String(index).padStart(2, "0")}`),
    captured_flow: { objective_id: "captured-adjacency-flow", status: "conclusive", total: 1, unit: "movimientos", horizon: "mes", contributions: [
      { first_station_id: "a", second_station_id: "b", total: 1 },
    ] },
  })) } as unknown as SrflResultSource;
  const getResultMetrics = vi.fn(async () => ({ status: "conclusive", total: 51, next_cursor: 50, summary: {}, rows: [{ case_id: "case-00", contribution: 1 }] }));
  render(<MetricsView host={{ getResultMetrics } as unknown as DomainUiHost} source={source} runId="run-reference" designId="d1" objectives={[
    { definition: { id: "captured-adjacency-flow", name: "Movimientos", unit: "movimientos/mes" } },
  ]} designTitles={[]} />);
  const card = await screen.findByRole("article", { name: "Adyacencias decisivas para un criterio" });
  fireEvent.change(within(card).getByRole("combobox"), { target: { value: "captured-adjacency-flow" } });
  await within(card).findByText("Página 1 de 2");
  expect(within(card).getAllByRole("row")).toHaveLength(51);
  expect(within(card).queryByRole("button", { name: "Ver más resultados" })).toBeNull();
  fireEvent.click(within(card).getByRole("button", { name: "Siguientes" }));
  await waitFor(() => expect(within(card).getAllByRole("row")).toHaveLength(2));
  expect(within(card).getByText("Alternativa 51")).toBeTruthy();
});
test("metric cards explain flexibility without raw fields or case IDs", async () => {
  const getResultMetrics = vi.fn(async ({ metric_id }: { metric_id: string }) => metric_id === "base-flexibility" ? {
    summary: { status: "conclusive", denominator: "1", base_layout_count: 20160, distribution: [{ from_percent: 0, to_percent: 25, count: 0 }, { from_percent: 25, to_percent: 50, count: 1 }, { from_percent: 50, to_percent: 75, count: 0 }, { from_percent: 75, to_percent: 100, count: 0 }] },
    status: "conclusive", total: 1,
    rows: [{ case_id: "case-reference", numerator: 1, denominator: 4, percent: "25" }],
    next_cursor: null,
  } : { summary: { status: "inconclusive" }, status: "inconclusive", total: 0, rows: [], next_cursor: null });
  render(<ResultSummary result={result} host={{ getResultMetrics } as unknown as DomainUiHost} onHome={() => undefined} />);
  fireEvent.click(screen.getByRole("tab", { name: "Métricas" }));
  const card = await screen.findByRole("article", { name: "Flexibilidad conservada frente a la base" });
  expect(within(card).getByText(/El 100 % equivale a la base: 20\.160 disposiciones/)).toBeTruthy();
  expect(within(card).getByRole("group", { name: "Distribución de flexibilidad de toda la frontera" })).toBeTruthy();
  expect(within(card).getByText("1 caso")).toBeTruthy();
  expect(within(card).getByText(/Caso 1/)).toBeTruthy();
  expect(card.textContent).not.toMatch(/case-reference|numerator|denominator|"status"|alternativa/u);
});
test("flexibility histogram uses the complete summary beyond the first page", async () => {
  const getResultMetrics = vi.fn(async ({ metric_id }: { metric_id: string }) => metric_id === "base-flexibility" ? {
    summary: { status: "conclusive", denominator: "52", base_layout_count: "100000000000000000000", distribution: [{ from_percent: 0, to_percent: 25, count: 11 }, { from_percent: 25, to_percent: 50, count: 11 }, { from_percent: 50, to_percent: 75, count: 10 }, { from_percent: 75, to_percent: 100, count: 20 }] },
    status: "conclusive", total: 52,
    rows: Array.from({ length: 50 }, (_, index) => ({ case_id: `case-${index}`, numerator: 1, denominator: 4 })),
    next_cursor: 50,
  } : { summary: { status: "inconclusive" }, status: "inconclusive", total: 0, rows: [], next_cursor: null });
  render(<ResultSummary result={result} host={{ getResultMetrics } as unknown as DomainUiHost} onHome={() => undefined} />);
  fireEvent.click(screen.getByRole("tab", { name: "Métricas" }));
  const card = await screen.findByRole("article", { name: "Flexibilidad conservada frente a la base" });
  expect(within(card).getByText("75 % a 100 %")).toBeTruthy();
  expect(within(card).getByText("20 casos")).toBeTruthy();
  expect(within(card).getByText(/Cada barra cuenta casos de la frontera de Pareto/)).toBeTruthy();
  expect(within(card).getByText("Ver cantidad exacta de la base")).toBeTruthy();
});

test("flexibility uses the same histogram with a small frontier", async () => {
  const getResultMetrics = vi.fn(async ({ metric_id }: { metric_id: string }) => metric_id === "base-flexibility" ? {
    summary: { status: "conclusive", denominator: "3", base_layout_count: 100, distribution: [{ from_percent: 0, to_percent: 25, count: 0 }, { from_percent: 25, to_percent: 50, count: 2 }, { from_percent: 50, to_percent: 75, count: 1 }, { from_percent: 75, to_percent: 100, count: 0 }] },
    status: "conclusive", total: 3,
    rows: [{ case_id: "a", numerator: 1, denominator: 4 }, { case_id: "b", numerator: 2, denominator: 8 }, { case_id: "c", numerator: 1, denominator: 2 }],
    next_cursor: null,
  } : { summary: { status: "inconclusive" }, status: "inconclusive", total: 0, rows: [], next_cursor: null });
  render(<ResultSummary result={result} host={{ getResultMetrics } as unknown as DomainUiHost} onHome={() => undefined} />);
  fireEvent.click(screen.getByRole("tab", { name: "Métricas" }));
  const card = await screen.findByRole("article", { name: "Flexibilidad conservada frente a la base" });
  expect(within(card).getByText("2 casos")).toBeTruthy();
  expect(within(card).getByText("1 caso")).toBeTruthy();
  expect(within(card).queryByRole("button", { name: /alternativa/u })).toBeNull();
});

test("flexibility reveals a low cluster without hiding the hundred-percent case", async () => {
  const getResultMetrics = vi.fn(async ({ metric_id }: { metric_id: string }) => metric_id === "base-flexibility" ? {
    summary: {
      status: "conclusive", denominator: "13", base_layout_count: 10000,
      distribution: [{ from_percent: 0, to_percent: 25, count: 12 }, { from_percent: 25, to_percent: 50, count: 0 }, { from_percent: 50, to_percent: 75, count: 0 }, { from_percent: 75, to_percent: 100, count: 1 }],
      focus_distribution: { upper_percent: 10, counts: [2, 4, 4, 2, 0], within_cases: 12, above_cases: 1 },
    },
    status: "conclusive", total: 13,
    rows: Array.from({ length: 12 }, (_, index) => ({ case_id: `low-${index}`, numerator: index % 7 + 1, denominator: 100 })).concat([{ case_id: "base", numerator: 1, denominator: 1 }]),
    next_cursor: null,
  } : { summary: { status: "inconclusive" }, status: "inconclusive", total: 0, rows: [], next_cursor: null });
  render(<ResultSummary result={result} host={{ getResultMetrics } as unknown as DomainUiHost} onHome={() => undefined} />);
  fireEvent.click(screen.getByRole("tab", { name: "Métricas" }));
  const card = await screen.findByRole("article", { name: "Flexibilidad conservada frente a la base" });
  const overview = within(card).getByRole("group", { name: "Distribución de flexibilidad de toda la frontera" });
  const focus = within(card).getByRole("group", { name: "Detalle de la concentración entre cero y 10 por ciento" });
  expect(within(overview).getByText("75 % a 100 %")).toBeTruthy();
  expect(within(overview).getByText("1 caso")).toBeTruthy();
  expect(within(focus).getByText("6 % a menos de 8 %")).toBeTruthy();
  expect(within(focus).getByText(/Fuera del tramo: 1 caso/)).toBeTruthy();
  expect(card.textContent).not.toContain("conservan al menos el 75 %");
});

test("flexibility detail opens the same case modal as the result detail view", async () => {
  const getResultMetrics = vi.fn(async ({ metric_id }: { metric_id: string }) => metric_id === "base-flexibility" ? {
    summary: { status: "conclusive", denominator: "1", base_layout_count: 12, distribution: [{ from_percent: 0, to_percent: 25, count: 0 }, { from_percent: 25, to_percent: 50, count: 0 }, { from_percent: 50, to_percent: 75, count: 0 }, { from_percent: 75, to_percent: 100, count: 1 }] },
    status: "conclusive", total: 1, rows: [{ case_id: "case-reference", numerator: 1, denominator: 1 }], next_cursor: null,
  } : { summary: { status: "inconclusive" }, status: "inconclusive", total: 0, rows: [], next_cursor: null });
  render(<ResultSummary result={result} host={{ getResultMetrics } as unknown as DomainUiHost} onHome={() => undefined} />);
  fireEvent.click(screen.getByRole("tab", { name: "Métricas" }));
  const card = await screen.findByRole("article", { name: "Flexibilidad conservada frente a la base" });
  fireEvent.click(within(card).getByText("Ver casos y porcentajes exactos"));
  fireEvent.click(await within(card).findByRole("button", { name: /Ver detalle de Caso 1/ }));
  const dialog = await screen.findByRole("dialog", { name: "Detalle del caso" });
  expect(within(dialog).getByText("Disponibilidad")).toBeTruthy();
  fireEvent.click(within(dialog).getByRole("button", { name: "Cerrar" }));
  expect(screen.getByRole("tab", { name: "Métricas" }).getAttribute("aria-selected")).toBe("true");
  expect(within(card).getByText("Ver casos y porcentajes exactos")).toBeTruthy();
});

test("flexibility detail opens an indexed fast case with its final classification", async () => {
  const indexedCase = caseResult("fast-frontier");
  indexedCase.pareto_classification = { ...indexedCase.pareto_classification, status: "inconclusive", pareto_optimal: null };
  const fast = {
    schema_version: "2.1.0", study_title: "Estudio rápido", study_description: null,
    stations: result.stations,
    execution: { domain_run_id: "run-fast-metric", domain_experiment_id: "b".repeat(64), mode: "high_performance" },
    generation: result.generation, objective_snapshots: result.objective_snapshots,
    designs: [{ design_id: "d1", design_title: "Diseño 1", valid_case_count: 1, invalid_combination_count: 0, pareto_case_count: 1, frontier_index: "frontier/design-0.u64", order_indexes: { case: "orders/design-0-case.u64" } }],
    limitations: [], files: {},
  } as unknown as FastResultSummaryV21;
  const getCaseDetail = vi.fn(async () => ({ case: indexedCase, equivalents: [indexedCase], equivalent_count: 1, next_offset: null }));
  const host = {
    getCasePage: async () => ({ items: [indexedCase], total: 1, page: 0, page_size: 50 }),
    getFrontier: async () => ({ items: [indexedCase], next_cursor: null }),
    getCaseDetail,
    getDominators: async () => ({ items: [], next_cursor: null }),
    getResultMetrics: async ({ metric_id }: { metric_id: string }) => metric_id === "base-flexibility" ? {
      summary: { status: "conclusive", denominator: "1", base_layout_count: 12, distribution: [{ from_percent: 0, to_percent: 25, count: 0 }, { from_percent: 25, to_percent: 50, count: 0 }, { from_percent: 50, to_percent: 75, count: 0 }, { from_percent: 75, to_percent: 100, count: 1 }] },
      status: "conclusive", total: 1, rows: [{ case_id: "fast-frontier", numerator: 1, denominator: 1 }], next_cursor: null,
    } : { summary: { status: "inconclusive" }, status: "inconclusive", total: 0, rows: [], next_cursor: null },
  } as unknown as DomainUiHost;
  render(<ResultSummary result={fast} host={host} onHome={() => undefined} />);
  fireEvent.click(screen.getByRole("tab", { name: "Métricas" }));
  const card = await screen.findByRole("article", { name: "Flexibilidad conservada frente a la base" });
  fireEvent.click(within(card).getByText("Ver casos y porcentajes exactos"));
  fireEvent.click(await within(card).findByRole("button", { name: /Ver detalle de Caso 1/ }));
  const dialog = await screen.findByRole("dialog", { name: "Detalle del caso" });
  expect(within(dialog).getByText("No dominado")).toBeTruthy();
  expect(getCaseDetail).toHaveBeenCalledWith({ domain_run_id: "run-fast-metric", case_id: "fast-frontier", equivalent_offset: 0 });
});

test("sensitivity identifies newly entering alternatives by components", async () => {
  const getResultMetrics = vi.fn(async ({ metric_id }: { metric_id: string }) => metric_id === "pareto-sensitivity" ? {
    summary: { status: "conclusive", official_frontier: 1, alternative_frontier: 2, excluded_criterion_id: "retained-compatible-layouts" },
    status: "conclusive", total: 1,
    rows: [{ case_id: "internal-case-id", added_component_ids: ["corte-ensamble"], status: "enters" }],
    next_cursor: null,
  } : { summary: { status: "inconclusive" }, status: "inconclusive", total: 0, rows: [], next_cursor: null });
  render(<ResultSummary result={result} host={{ getResultMetrics } as unknown as DomainUiHost} onHome={() => undefined} />);
  fireEvent.click(screen.getByRole("tab", { name: "Métricas" }));
  const card = screen.getByRole("article", { name: "Sensibilidad de Pareto a un criterio" });
  fireEvent.change(within(card).getByRole("combobox"), { target: { value: "retained-compatible-layouts" } });
  expect(await within(card).findByText("Alternativa con corte-ensamble")).toBeTruthy();
  expect(card.textContent).not.toContain("internal-case-id");
});
test("fast Pareto chart draws the exact frontier while grouped projection is pending", async () => {
  const pendingProjection = new Promise<PlotProjectionResult>(() => undefined);
  render(<IndexedParetoChart
    objectives={[{ id: "retained-compatible-layouts", label: "Flexibilidad" }]}
    frontierCases={[caseResult("frontier-fast")]}
    loadPoints={async () => []}
    loadProjection={async () => pendingProjection}
    onSelectCaseId={() => undefined}
  />);
  expect(screen.getByRole("button", { name: /frontier-fast: No dominado/ })).toBeTruthy();
  expect(await screen.findByText(/Preparando alternativas dominadas; la frontera usa ejes lineales provisorios/)).toBeTruthy();
});
test("design comparison keeps a Pareto summary, draws the frontier and sorts every valid case", () => {
  const first = caseResult("case-a");
  first.retained_layouts!.fraction = { numerator: 1, denominator: 3 };
  const second = caseResult("case-b");
  second.retained_layouts!.fraction = { numerator: 2, denominator: 3 };
  const dominated = caseResult("case-c");
  dominated.retained_layouts!.fraction = { numerator: 0, denominator: 3 };
  dominated.pareto_classification = {
    status: "conclusive",
    pareto_optimal: false,
    dominated: true,
    objective_refs: ["retained-compatible-layouts"],
  };
  const { container } = render(
    <DesignComparison
      cases={[second, dominated, first]}
      objectiveAliases={{
        "retained-compatible-layouts": "Disposiciones compatibles conservadas",
      }}
      onSelect={() => undefined}
    />,
  );
  const paretoTable = screen.getByRole("region", { name: "Resumen de casos no dominados" });
  expect(within(paretoTable).getAllByRole("row")).toHaveLength(3);
  const paretoValues = () =>
    within(paretoTable)
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell")[0]?.textContent?.slice(0, 6));
  expect(paretoValues()).toEqual(["case-a", "case-b"]);
  expect(
    container.querySelector("polyline.srfl-pareto-frontier"),
  ).not.toBeNull();
  expect(screen.getByRole("img").getAttribute("viewBox")).toBe("0 0 600 390");
  const table = screen.getByRole("region", { name: "Todos los casos válidos" });
  const values = () =>
    within(table)
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell")[0]?.textContent);
  expect(values()).toEqual(["case-a", "case-b", "case-c"]);
  expect(
    screen.getAllByText("Disposiciones compatibles conservadas").length,
  ).toBeGreaterThan(1);
  expect(screen.getAllByText("0,333333").length).toBeGreaterThan(1);
  expect(screen.queryByText("1/3")).toBeNull();
  fireEvent.click(within(paretoTable).getByRole("button", { name: /Disposiciones compatibles conservadas/ }));
  fireEvent.click(within(paretoTable).getByRole("button", { name: /Disposiciones compatibles conservadas/ }));
  expect(paretoValues()).toEqual(["case-b", "case-a"]);
  fireEvent.click(
    within(table).getByRole("button", {
      name: /Disposiciones compatibles conservadas/,
    }),
  );
  fireEvent.click(
    within(table).getByRole("button", {
      name: /Disposiciones compatibles conservadas/,
    }),
  );
  expect(values()).toEqual(["case-b", "case-a", "case-c"]);
});
test("equivalent component selections are shown as one physical alternative", () => {
  const first = caseResult("case-a");
  const equivalent = caseResult("case-b");
  equivalent.forest_id = first.forest_id;
  equivalent.component_ids = ["c1", "redundant-path"];
  equivalent.added_component_ids = ["redundant-path"];
  render(
    <DesignComparison
      cases={[first, equivalent]}
      onSelect={() => undefined}
    />,
  );
  const table = screen.getByRole("region", { name: "Todos los casos válidos" });
  expect(within(table).getAllByRole("row")).toHaveLength(2);
  expect(within(table).getByText("2 selecciones equivalentes")).toBeTruthy();
});
test("each adjacency matrix becomes an independent sortable result dimension", () => {
  const item = caseResult("case-matrices") as LayoutCaseResultV2 & { adjacency_values: unknown[] };
  item.adjacency_values = [
    { objective_id: "adjacency-beneficio", objective_version: "1", matrix_id: "beneficio", status: "conclusive", total: "12.50", unit: "puntos", reference_period: null, directed: false, direction: "maximize", contributions: [] },
    { objective_id: "adjacency-costo", objective_version: "1", matrix_id: "costo", status: "conclusive", total: "8.25", unit: "ARS", reference_period: "mes", directed: false, direction: "minimize", contributions: [] },
  ];
  item.pareto_classification.objective_refs = ["retained-compatible-layouts", "adjacency-beneficio", "adjacency-costo"];
  render(<DesignComparison cases={[item]} objectiveAliases={{ "adjacency-beneficio": "Beneficio · ↑ Maximizar", "adjacency-costo": "Costo · ↓ Minimizar" }} onSelect={() => undefined} />);
  const table = screen.getByRole("region", { name: "Todos los casos válidos" });
  expect(within(table).getByRole("button", { name: /Beneficio · ↑ Maximizar/ })).toBeTruthy();
  expect(within(table).getByRole("button", { name: /Costo · ↓ Minimizar/ })).toBeTruthy();
  expect(within(table).getByText("12.50 puntos")).toBeTruthy();
  expect(within(table).getByText("8.25 ARS\/mes")).toBeTruthy();
});
test("v1 results open in a labelled read-only historical viewer", () => {
  const historical = {
    ...result,
    schema_version: "1.0.0",
    domain: { id: "single-row-facility-layout", version: "1.0.0" },
    generation: {
      theoretical_combinations: 1,
      valid_selections: 1,
      invalid_combinations: 0,
    },
    designs: [
      {
        design_id: "d1",
        design_title: "Histórico",
        cases: [
          {
            case_id: "old",
            availability_ratio: { numerator: 1, denominator: 2 },
            restrictiveness_ratio: { numerator: 1, denominator: 3 },
            total_utility: 4,
            pareto_optimal: true,
            dominated: false,
          },
        ],
      },
    ],
  } as unknown as SingleRowFacilityLayoutResult;
  render(<ResultSummary result={historical} onHome={() => undefined} />);
  expect(
    screen.getByText(/Histórico · SRFL 1.0.0 · sólo lectura/),
  ).toBeTruthy();
  expect(screen.getByText("Utilidad histórica")).toBeTruthy();
  expect(screen.queryByText("Guardar como plantilla")).toBeNull();
});
