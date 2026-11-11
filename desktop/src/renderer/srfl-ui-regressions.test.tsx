import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, test } from "vitest";
import type { LayoutCaseResultV2 } from "@domain-ui-sdk";
import { DesignComparison } from "@srfl-ui/components/results/DesignComparison";
import { CaseDetail } from "@srfl-ui/components/results/CaseDetail";
import { AdjacenciesStep } from "@srfl-ui/components/wizard/AdjacenciesStep";
import { createEmptyDraft } from "@srfl-ui/config/defaults";

afterEach(() => document.body.replaceChildren());

function multiObjectiveCase(): LayoutCaseResultV2 {
  return {
    case_id: "case-multi",
    core_run_id: "core",
    design_id: "design",
    component_ids: ["a-b"],
    mandatory_component_ids: [],
    added_component_ids: ["a-b"],
    compatible_layout_count: {
      value: 6,
      exact_value: 6,
      reference_value: 6,
      comparison_status: "match",
      counting_convention: "undirected_paths_reverse_identified",
      method: null,
    },
    forest_id: "forest",
    forest_structure: { paths: [["a", "b"]], isolated_station_ids: ["c"] },
    edges: [["a", "b"]],
    prescribed_edge_count: 1,
    feasibility: "feasible",
    diagnostics: [],
    limitations: [],
    technical_metrics: null,
    findings: [],
    retained_layouts: {
      objective_id: "retained-compatible-layouts",
      objective_version: "1",
      direction: "maximize",
      unit: "fracción exacta",
      status: "conclusive",
      compatible_layout_count: 6,
      base_layout_count: 12,
      fraction: { numerator: 1, denominator: 2 },
    },
    rel_closeness: [
      {
        objective_id: "rel-closeness-a",
        objective_version: "1",
        direction: "maximize",
        unit: "fracción exacta",
        status: "conclusive",
        level: "A",
        numerator: 1,
        denominator: 2,
        fraction: { numerator: 1, denominator: 2 },
        guaranteed_pairs: [["a", "b"]],
        pending_pairs: [],
      },
    ],
    pareto_classification: {
      status: "conclusive",
      pareto_optimal: true,
      dominated: false,
      objective_refs: ["retained-compatible-layouts", "rel-closeness-a"],
    },
  };
}

test("Pareto axes remain distinct and the preview opens a large graph", () => {
  const nonDominated = multiObjectiveCase();
  const dominated = multiObjectiveCase();
  dominated.case_id = "case-dominated";
  dominated.forest_id = "forest-dominated";
  dominated.retained_layouts!.fraction = { numerator: 0, denominator: 1 };
  dominated.rel_closeness![0]!.fraction = { numerator: 1, denominator: 4 };
  dominated.rel_closeness![0]!.numerator = 1;
  dominated.rel_closeness![0]!.denominator = 4;
  dominated.pareto_classification = {
    ...dominated.pareto_classification,
    pareto_optimal: false,
    dominated: true,
  };
  const { container } = render(
    <DesignComparison
      cases={[nonDominated, dominated]}
      onSelect={() => undefined}
    />,
  );
  expect(container.querySelector("rect.is-pareto")).not.toBeNull();
  expect(container.querySelector("circle.is-dominated")).not.toBeNull();
  const x = screen.getByRole("combobox", {
    name: "Eje X",
  }) as HTMLSelectElement;
  const y = screen.getByRole("combobox", {
    name: "Eje Y",
  }) as HTMLSelectElement;
  expect(x.classList.contains("ui-input")).toBe(true);
  expect(y.classList.contains("ui-input")).toBe(true);
  expect(x.value).not.toBe(y.value);
  fireEvent.change(x, { target: { value: y.value } });
  expect(x.value).not.toBe(y.value);
  fireEvent.click(screen.getByRole("button", { name: "Ampliar gráfico" }));
  const dialog = screen.getByRole("dialog", {
    name: "Explorador de la frontera de Pareto",
  });
  expect(within(dialog).getByRole("combobox", { name: "Eje X" })).toBeTruthy();
  expect(within(dialog).getByRole("combobox", { name: "Eje Y" })).toBeTruthy();
  expect(
    within(dialog)
      .getByRole("combobox", { name: "Eje X" })
      .classList.contains("ui-input"),
  ).toBe(true);
  expect(within(dialog).getByRole("img").getAttribute("viewBox")).toBe(
    "0 0 1200 720",
  );
  expect(dialog.querySelector(".srfl-point-label")).toBeNull();
  expect(dialog.querySelectorAll(".srfl-axis-tick").length).toBeGreaterThan(5);
  const xScale = within(dialog).getByRole("combobox", { name: "Transformación X" });
  const yScale = within(dialog).getByRole("combobox", { name: "Transformación Y" });
  expect((xScale as HTMLSelectElement).value).toBe("automatic");
  expect(["linear", "square-root", "adjusted-log", "percentile"]).toContain(
    within(dialog).getByRole("img").getAttribute("data-x-scale"),
  );
  expect(within(xScale).getByRole("option", { name: "Raíz cuadrada" })).toBeTruthy();
  expect(within(xScale).getByRole("option", { name: "Logarítmica ajustada" })).toBeTruthy();
  expect(within(yScale).getByRole("option", { name: "Percentiles" })).toBeTruthy();
  fireEvent.change(xScale, { target: { value: "linear" } });
  const linearTicks = [
    ...dialog.querySelectorAll(".srfl-axis-tick:not(.srfl-axis-tick--y)"),
  ].map((node) => node.textContent);
  expect(linearTicks[0]).toBe("0,25");
  expect(linearTicks.at(-1)).toBe("0,5");
  fireEvent.change(xScale, { target: { value: "square-root" } });
  const rootTicks = [
    ...dialog.querySelectorAll(".srfl-axis-tick:not(.srfl-axis-tick--y)"),
  ].map((node) => node.textContent);
  expect(rootTicks[0]).toBe("0,25");
  expect(rootTicks.at(-1)).toBe("0,5");
  expect(rootTicks).not.toEqual(linearTicks);
  fireEvent.change(xScale, { target: { value: "adjusted-log" } });
  const k = within(dialog).getByRole("spinbutton", { name: "k X" });
  expect((k as HTMLInputElement).value).toBe("100");
  const logarithmicTicksAt100 = [
    ...dialog.querySelectorAll(".srfl-axis-tick:not(.srfl-axis-tick--y)"),
  ].map((node) => node.textContent);
  fireEvent.change(k, { target: { value: "10" } });
  const logarithmicTicksAt10 = [
    ...dialog.querySelectorAll(".srfl-axis-tick:not(.srfl-axis-tick--y)"),
  ].map((node) => node.textContent);
  expect(logarithmicTicksAt10[0]).toBe("0,25");
  expect(logarithmicTicksAt10.at(-1)).toBe("0,5");
  expect(logarithmicTicksAt10).not.toEqual(logarithmicTicksAt100);
  fireEvent.change(xScale, { target: { value: "percentile" } });
  expect((xScale as HTMLSelectElement).value).toBe("percentile");
  expect(within(dialog).getByRole("img").getAttribute("data-x-scale")).toBe("percentile");
  expect(document.querySelector('.srfl-result-chart svg[role="img"]')?.getAttribute("data-x-scale")).toBe("percentile");
  expect(within(dialog).queryByRole("button", { name: "Acercar" })).toBeNull();
  expect(
    within(dialog).getByRole("img").getAttribute("preserveAspectRatio"),
  ).toBe("xMidYMid meet");
});

test("case detail restores the readable forest diagram", () => {
  render(
    <CaseDetail
      item={multiObjectiveCase()}
      stations={[
        { id: "a", name: "Estación A" },
        { id: "b", name: "Estación B" },
        { id: "c", name: "Estación C" },
      ]}
      onClose={() => undefined}
    />,
  );
  const diagram = screen.getByRole("img", {
    name: "Bosque de restricciones y adyacencias del caso",
  });
  expect(within(diagram).getByText("Estación A")).toBeTruthy();
  expect(within(diagram).getByText("Estación C")).toBeTruthy();
  expect(screen.getByText("Identificación y estado")).toBeTruthy();
  expect(screen.getByText("Cobertura de prioridades de cercanía")).toBeTruthy();
  expect(screen.getByText("Incluidas como adyacencia obligatoria")).toBeTruthy();
  expect(screen.getByText("No incluidas")).toBeTruthy();
  expect(screen.queryByText("Garantizados")).toBeNull();
  expect(screen.queryByText("Pendientes")).toBeNull();
  expect(screen.getAllByText("1/2 = 0,5").length).toBeGreaterThan(0);
  expect(screen.queryByText("Factibilidad")).toBeNull();
  expect(screen.queryByText("feasible")).toBeNull();
  expect(screen.queryByText("Estado")).toBeNull();
  expect(screen.queryByText("conclusive")).toBeNull();
});

test("case detail identifies recurring exact decimals", () => {
  const item = multiObjectiveCase();
  item.retained_layouts!.fraction = { numerator: 1, denominator: 6 };
  render(<CaseDetail item={item} stations={[]} onClose={() => undefined} />);
  const repeating = document.querySelector(".srfl-repeating-decimal");
  expect(repeating?.textContent).toBe("6");
  expect(repeating?.parentElement?.textContent).toBe("1/6 = 0,16");
  expect(repeating?.textContent).not.toContain("\u0302");
});

test("case detail groups dominance differences in an interactive comparison", () => {
  const item = multiObjectiveCase();
  const first = "0318a5b199eac1e69fe5ac448de13c0f475ebe1c53b52321e3c63fd8ab9aa610";
  const second = "2a3c2eab391c4079c54d228e95531503fd2035d2958850898cd82aa734a78a14";
  item.pareto_classification = {
    ...item.pareto_classification,
    pareto_optimal: false,
    dominated: true,
    dominated_by_case_ids: [second, first],
    differences: [
      { objective_id: "matrix-benefit", preferred_case_id: first, preferred_value: { numerator: 17, denominator: 1 }, other_case_id: item.case_id, other_value: { numerator: 8, denominator: 1 } },
      { objective_id: "matrix-cost", preferred_case_id: first, preferred_value: { numerator: 14, denominator: 1 }, other_case_id: item.case_id, other_value: { numerator: 24, denominator: 1 } },
      { objective_id: "matrix-benefit", preferred_case_id: second, preferred_value: { numerator: 12, denominator: 1 }, other_case_id: item.case_id, other_value: { numerator: 8, denominator: 1 } },
    ],
  };
  render(<CaseDetail
    item={item}
    stations={[]}
    objectiveAliases={{ "matrix-benefit": "Producción · ↑ Maximizar", "matrix-cost": "Costo · ↓ Minimizar" }}
    objectiveDirections={{ "matrix-benefit": "maximize", "matrix-cost": "minimize" }}
    onClose={() => undefined}
  />);

  expect(screen.getByText("2 alternativas")).toBeTruthy();
  expect(screen.getByRole("button", { name: /0318a5b199ea/ }).getAttribute("aria-pressed")).toBe("true");
  const alternatives = within(screen.getByRole("navigation", { name: "Alternativas dominantes" })).getAllByRole("button");
  expect(alternatives[0]?.textContent).toContain("0318a5b199ea");
  expect(alternatives[0]?.textContent).toContain("2 mejoras");
  expect(screen.getByText("Aumenta en un 112,5 %")).toBeTruthy();
  expect(screen.getByText("Disminuye en un 41,67 %")).toBeTruthy();
  expect(screen.queryByText(/^Dominado por/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /2a3c2eab391c/ }));
  expect(screen.getByText("Aumenta en un 50 %")).toBeTruthy();
});

test("flexibility comparison shows compatible counts while keeping percent improvement", () => {
  const item = multiObjectiveCase();
  const preferred = multiObjectiveCase();
  preferred.case_id = "preferred";
  item.retained_layouts!.compatible_layout_count = 23040;
  item.retained_layouts!.base_layout_count = 10461394944000;
  preferred.retained_layouts!.compatible_layout_count = 92160;
  item.pareto_classification = {
    ...item.pareto_classification,
    dominated_by_case_ids: ["preferred"],
    differences: [{ objective_id: "retained-compatible-layouts", preferred_case_id: "preferred", preferred_value: { numerator: 1, denominator: 90090 }, other_case_id: item.case_id, other_value: { numerator: 1, denominator: 360360 } }],
  };
  render(<CaseDetail item={item} cases={[item, preferred]} stations={[]} onClose={() => undefined} />);
  const table = screen.getByRole("table");
  expect(within(table).getByText("23.040")).toBeTruthy();
  expect(within(table).getByText("92.160")).toBeTruthy();
  expect(within(table).getByText("Aumenta en un 300 %")).toBeTruthy();
});

function AdjacencyHarness() {
  const initial = createEmptyDraft();
  initial.study.stations = [
    { clientKey: "a", id: "a", idManuallyEdited: true, name: "A" },
    { clientKey: "b", id: "b", idManuallyEdited: true, name: "B" },
  ];
  const [draft, setDraft] = useState(initial);
  return <AdjacenciesStep draft={draft} onChange={setDraft} />;
}

function PriorityAdjacencyHarness() {
  const initial = createEmptyDraft();
  initial.study.stations = [
    { clientKey: "a", id: "a", idManuallyEdited: true, name: "Recepción" },
    { clientKey: "b", id: "b", idManuallyEdited: true, name: "Despacho" },
  ];
  initial.decisionModel.relCloseness = [
    {
      firstStationId: "a",
      secondStationId: "b",
      level: "A",
      reason: "Intercambio continuo",
      provenance: "equipo operativo",
    },
  ];
  initial.decisionModel.adjacencyMatrices = [{
    id: "movimientos", name: "Movimientos", description: "Movimientos entre áreas", direction: "maximize",
    directed: false,
    unit: "viajes",
    referencePeriod: "turno",
    provenance: "medición",
    entries: [{ fromStationId: "a", toStationId: "b", value: "24" }],
  }];
  const [draft, setDraft] = useState(initial);
  return <AdjacenciesStep draft={draft} onChange={setDraft} />;
}

test("a REL priority can become a candidate restriction with its flow visible", () => {
  render(<PriorityAdjacencyHarness />);
  expect(screen.getByText("Recepción ↔ Despacho")).toBeTruthy();
  expect(screen.getByText("Nivel REL A")).toBeTruthy();
  expect(screen.getByText("24 viajes/turno")).toBeTruthy();
  fireEvent.click(
    screen.getByRole("button", { name: "Crear restricción candidata" }),
  );
  expect(screen.getByText("Disponible en las alternativas")).toBeTruthy();
  expect(screen.getByText(/Restricciones agregadas · 1/)).toBeTruthy();
});

test("a restriction cannot be added twice in either direction", () => {
  render(<AdjacencyHarness />);
  const diagram = screen.getByRole("img", {
    name: "Diagrama interactivo de adyacencias",
  });
  fireEvent.click(within(diagram).getByText("a"));
  fireEvent.click(within(diagram).getByText("b"));
  fireEvent.click(screen.getByRole("button", { name: "Agregar restricción candidata" }));
  fireEvent.click(within(diagram).getByText("b"));
  fireEvent.click(within(diagram).getByText("a"));
  fireEvent.click(screen.getByRole("button", { name: "Agregar restricción candidata" }));
  expect(screen.getByRole("status").textContent).toContain("ya existe");
  expect(screen.getByText(/Restricciones agregadas · 1/)).toBeTruthy();
});
