import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { ConfigurationOption } from "@domain-ui-kit";
import { SRFL_CONFIGURATION_SECTIONS } from "@srfl-ui/config/advanced-options";
import { RelationsStep } from "@srfl-ui/components/wizard/RelationsStep";
import { DesignsStep } from "@srfl-ui/components/wizard/DesignsStep";
import { ReviewStep } from "@srfl-ui/components/wizard/ReviewStep";
import { StationTable } from "@srfl-ui/components/stations/StationTable";
import { createEmptyDraft } from "@srfl-ui/config/defaults";
import { SrflEditorStep } from "@srfl-ui/model/editor-state.types";
import { validateStep } from "@srfl-ui/model/validation";
import { toScientificDraft } from "@srfl-ui/model/mappers";

afterEach(cleanup);

test.each(["2.0.0", "2.1.0"] as const)("%s accepts signed and zero candidate values without relaxing matrix validation", (version) => {
  const draft = draftWithDecisionMatrices();
  draft.schemaVersion = version;
  draft.study.components = [{ clientKey: "ab", id: "a-b", idManuallyEdited: true, stationIds: ["a", "b"] }];
  draft.decisionModel.relCloseness = null;
  draft.decisionModel.undesiredPrescribedAdjacencies = [];
  draft.decisionModel.selectedObjectives = [{ id: "captured-adjacency-flow", version: "1" }];
  for (const direction of ["maximize", "minimize"] as const) {
    draft.decisionModel.adjacencyMatrices[0]!.direction = direction;
    for (const value of ["-1.25", "0", "2.5"]) {
      draft.decisionModel.adjacencyMatrices[0]!.entries[0]!.value = value;
      expect(validateStep(draft, SrflEditorStep.Adjacencies)).toEqual([]);
      expect(validateStep(draft, SrflEditorStep.Relations)).toEqual([]);
    }
  }
  draft.decisionModel.adjacencyMatrices[0]!.entries[0]!.value = "bad";
  expect(validateStep(draft, SrflEditorStep.Relations).length).toBeGreaterThan(0);
  draft.decisionModel.adjacencyMatrices[0]!.entries = [];
  expect(validateStep(draft, SrflEditorStep.Relations).length).toBeGreaterThan(0);
});

test("advanced options are rendered from typed definitions and update the draft", () => {
  const definition = SRFL_CONFIGURATION_SECTIONS.find(
    (section) => section.id === "problem-limits",
  )!.options[0]!;
  const draft = createEmptyDraft();
  let updated = draft;
  render(
    <ConfigurationOption
      definition={definition}
      draft={draft}
      onChange={(value) => {
        updated = value;
      }}
    />,
  );
  expect(screen.getByText("execution.integer_limits.max_n")).toBeTruthy();
  fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "9" } });
  expect(updated.execution.integer_limits.max_n).toBe(9);
});

test("a single control design can be created without mandatory restrictions", () => {
  const draft = createEmptyDraft();
  draft.study.components = [{ clientKey: "component-a-b", id: "a-b", idManuallyEdited: false, stationIds: ["a", "b"] }];
  let updated = draft;
  const view = render(<DesignsStep draft={draft} onChange={(value) => { updated = value; }} />);
  fireEvent.click(screen.getByRole("button", { name: /Agregar dise/ }));
  fireEvent.click(screen.getByRole("switch", { name: /control/ }));
  fireEvent.click(screen.getByRole("button", { name: "Agregar" }));
  expect(updated.study.designs).toHaveLength(1);
  expect(updated.study.designs[0]?.baseComponentIds).toEqual([]);
  expect(validateStep(updated, SrflEditorStep.Designs)).toEqual([]);
  view.rerender(<DesignsStep draft={updated} onChange={(value) => { updated = value; }} />);
  fireEvent.click(screen.getByRole("button", { name: /Agregar dise/ }));
  expect(screen.getByRole("switch", { name: /control/ }).hasAttribute("disabled")).toBe(true);
});

test("design validation rejects more than one control", () => {
  const draft = createEmptyDraft();
  draft.study.designs = [
    { clientKey: "control-1", id: "control-1", idManuallyEdited: false, title: "Control 1", baseComponentIds: [] },
    { clientKey: "control-2", id: "control-2", idManuallyEdited: false, title: "Control 2", baseComponentIds: [] },
  ];
  expect(validateStep(draft, SrflEditorStep.Designs).map((item) => item.message).some((message) => message.includes("control sin restricciones obligatorias"))).toBe(true);
});

function draftWithDecisionMatrices() {
  const draft = createEmptyDraft();
  draft.study.stations = [
    { clientKey: "station-a", id: "a", idManuallyEdited: true, name: "A" },
    { clientKey: "station-b", id: "b", idManuallyEdited: true, name: "B" },
  ];
  draft.decisionModel.relCloseness = [
    {
      firstStationId: "a",
      secondStationId: "b",
      level: "X",
      reason: "Separar",
      provenance: "estudio",
    },
  ];
  draft.decisionModel.adjacencyMatrices = [{
    id: "movimientos", name: "Movimientos", description: "Movimientos entre áreas", direction: "maximize",
    directed: false,
    unit: "viajes",
    referencePeriod: "día",
    provenance: "medición",
    entries: [{ fromStationId: "a", toStationId: "b", value: "0" }],
  }];
  return draft;
}

test("REL and flow imports remain explicit when both matrices are active", () => {
  const draft = draftWithDecisionMatrices();
  let updated = draft;
  render(
    <RelationsStep
      draft={draft}
      onChange={(value) => {
        updated = value;
      }}
    />,
  );
  fireEvent.click(screen.getByRole("tab", { name: /Matrices cuantitativas/ }));
  fireEvent.change(screen.getByLabelText("Datos tabulares"), {
    target: { value: ";A;B\nA;—;17\nB;17;—" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Aplicar datos" }));
  expect(updated.decisionModel.adjacencyMatrices[0]?.entries[0]?.value).toBe("17");
  expect(updated.decisionModel.relCloseness?.[0]?.level).toBe("X");
});

test("creating an X policy does not invent scientific evidence", () => {
  const draft = draftWithDecisionMatrices();
  let updated = draft;
  render(
    <RelationsStep
      draft={draft}
      onChange={(value) => {
        updated = value;
      }}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Sólo advertir" }));
  expect(updated.decisionModel.undesiredPrescribedAdjacencies).toEqual([
    {
      firstStationId: "a",
      secondStationId: "b",
      cause: "",
      explanation: "",
      provenance: "",
      policy: "warn",
    },
  ]);
});

test("changing an X relation removes its now-invalid policy", () => {
  const draft = draftWithDecisionMatrices();
  draft.decisionModel.undesiredPrescribedAdjacencies = [
    {
      firstStationId: "a",
      secondStationId: "b",
      cause: "safety",
      explanation: "Separar",
      provenance: "norma",
      policy: "warn",
    },
  ];
  let updated = draft;
  render(
    <RelationsStep
      draft={draft}
      onChange={(value) => {
        updated = value;
      }}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Lista" }));
  fireEvent.change(screen.getByDisplayValue("X"), { target: { value: "U" } });
  expect(updated.decisionModel.relCloseness?.[0]?.level).toBe("U");
  expect(updated.decisionModel.undesiredPrescribedAdjacencies).toEqual([]);
});

test("station changes reconcile REL and flow matrices immediately", () => {
  const draft = draftWithDecisionMatrices();
  let updated = draft;
  render(
    <StationTable
      draft={draft}
      onChange={(value) => {
        updated = value;
      }}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Agregar estación" }));
  expect(updated.study.stations).toHaveLength(3);
  expect(updated.decisionModel.relCloseness).toHaveLength(3);
  expect(updated.decisionModel.adjacencyMatrices[0]?.entries).toHaveLength(3);
});

test("station import uses matrix headers and removes references to replaced stations", () => {
  const draft = draftWithDecisionMatrices();
  let updated = draft;
  render(<StationTable draft={draft} onChange={(value) => { updated = value; }} />);
  fireEvent.click(screen.getByText("Importar estaciones"));
  fireEvent.change(screen.getByLabelText("Datos tabulares"), { target: { value: ";A;C\nA;—;not-a-number\nC;U;—" } });
  fireEvent.click(screen.getByRole("button", { name: "Aplicar estaciones" }));
  expect(updated.study.stations.map((station) => station.name)).toEqual(["A", "C"]);
  expect(updated.study.components.every((component) => component.stationIds.every((id) => id !== "b"))).toBe(true);
});

test("station IDs and aliases are copyable but read-only", () => {
  const draft = draftWithDecisionMatrices();
  render(<StationTable draft={draft} onChange={() => undefined} />);
  expect(screen.getByLabelText("ID de A").hasAttribute("readonly")).toBe(true);
  expect(screen.getByLabelText("Alias de A").hasAttribute("readonly")).toBe(true);
  expect(screen.getByLabelText("Alias de A").getAttribute("value")).toBe("A");
});

test("changing an X policy keeps its evidence", () => {
  const draft = draftWithDecisionMatrices();
  draft.decisionModel.undesiredPrescribedAdjacencies = [
    {
      firstStationId: "a",
      secondStationId: "b",
      cause: "safety",
      explanation: "Separar",
      provenance: "norma",
      policy: "warn",
    },
  ];
  let updated = draft;
  render(
    <RelationsStep
      draft={draft}
      onChange={(value) => {
        updated = value;
      }}
    />,
  );
  fireEvent.change(screen.getByDisplayValue("Advertir"), {
    target: { value: "forbidden" },
  });
  expect(updated.decisionModel.undesiredPrescribedAdjacencies).toEqual([
    {
      firstStationId: "a",
      secondStationId: "b",
      cause: "safety",
      explanation: "Separar",
      provenance: "norma",
      policy: "forbidden",
    },
  ]);
});

test("adjacency validation rejects criteria that can only remain zero", () => {
  const draft = draftWithDecisionMatrices();
  draft.decisionModel.selectedObjectives = [
    { id: "rel-closeness", version: "1" },
    { id: "captured-adjacency-flow", version: "1" },
  ];
  draft.decisionModel.relCloseness![0]!.level = "A";
  draft.decisionModel.adjacencyMatrices[0]!.entries[0]!.value = "4";
  const blocked = validateStep(draft, SrflEditorStep.Adjacencies);
  expect(blocked.map((item) => item.message)).toContain(
    "El nivel REL A no puede variar: convertí al menos una de sus relaciones en restricción candidata.",
  );
  draft.study.components = [
    {
      clientKey: "component-a-b",
      id: "a-b",
      idManuallyEdited: false,
      stationIds: ["a", "b"],
    },
  ];
  expect(validateStep(draft, SrflEditorStep.Adjacencies)).toEqual([]);
});

test("quantitative matrices can be duplicated and receive independent objectives", () => {
  const draft = draftWithDecisionMatrices();
  let updated = draft;
  const view = render(<RelationsStep draft={draft} onChange={(value) => { updated = value; }} />);
  fireEvent.click(screen.getByRole("tab", { name: /Matrices cuantitativas/ }));
  fireEvent.change(screen.getByLabelText("Objetivo"), { target: { value: "minimize" } });
  expect(updated.decisionModel.adjacencyMatrices[0]?.direction).toBe("minimize");
  view.rerender(<RelationsStep draft={updated} onChange={(value) => { updated = value; }} />);
  fireEvent.click(screen.getByRole("button", { name: "Duplicar matriz" }));
  expect(updated.decisionModel.adjacencyMatrices).toHaveLength(2);
  expect(new Set(updated.decisionModel.adjacencyMatrices.map((item) => item.id)).size).toBe(2);
  expect(updated.decisionModel.adjacencyMatrices[1]?.id).toBe("1");
});

test("quantitative matrices use nested tabs and edit numeric cells on double click", () => {
  const draft = draftWithDecisionMatrices();
  let updated = draft;
  const view = render(<RelationsStep draft={draft} onChange={(value) => { updated = value; }} />);
  fireEvent.click(screen.getByRole("tab", { name: /Matrices cuantitativas/ }));

  expect(screen.getByRole("tab", { name: /Movimientos.*Maximizar/ })).toBeTruthy();
  expect(screen.queryByLabelText("Identificador estable")).toBeNull();
  const matrixCell = screen.getByRole("button", { name: "A, B" });
  fireEvent.click(matrixCell);
  fireEvent.doubleClick(matrixCell);
  const directCellInput = screen.getByLabelText("Movimientos: A → B");
  expect(directCellInput.closest("td")?.classList.contains("ui-matrix__editable-cell")).toBe(true);
  fireEvent.change(directCellInput, { target: { value: "23.5" } });
  fireEvent.keyDown(directCellInput, { key: "Enter" });
  expect(updated.decisionModel.adjacencyMatrices[0]?.entries[0]?.value).toBe("23.5");
  expect(screen.queryByRole("heading", { name: "a → b" })).toBeNull();

  fireEvent.click(screen.getByRole("button", { name: "Agregar matriz" }));
  expect(updated.decisionModel.adjacencyMatrices).toHaveLength(2);
  expect(updated.decisionModel.adjacencyMatrices[1]?.id).toBe("1");
  view.rerender(<RelationsStep draft={updated} onChange={(value) => { updated = value; }} />);
  expect(screen.getByRole("tab", { name: /Matriz 1.*Maximizar/ })).toBeTruthy();
});

test("non-directed matrices are canonicalized before reaching the gateway", () => {
  const draft = draftWithDecisionMatrices();
  draft.study.stations = [draft.study.stations[1]!, draft.study.stations[0]!];
  draft.decisionModel.adjacencyMatrices[0]!.entries = [
    { fromStationId: "b", toStationId: "a", value: "9" },
  ];
  const scientific = toScientificDraft(draft);
  const matrices = scientific.decision_model.adjacency_flow;
  expect(Array.isArray(matrices)).toBe(true);
  expect((matrices as unknown as { entries: { from_station_id: string; to_station_id: string }[] }[])[0]?.entries[0]).toMatchObject({
    from_station_id: "a",
    to_station_id: "b",
  });
});

test("turning direction off creates canonical pairs regardless of station order", () => {
  const draft = draftWithDecisionMatrices();
  draft.study.stations = [draft.study.stations[1]!, draft.study.stations[0]!];
  draft.decisionModel.adjacencyMatrices[0]!.directed = true;
  draft.decisionModel.adjacencyMatrices[0]!.entries = [
    { fromStationId: "b", toStationId: "a", value: "8" },
    { fromStationId: "a", toStationId: "b", value: "9" },
  ];
  let updated = draft;
  render(<RelationsStep draft={draft} onChange={(value) => { updated = value; }} />);
  fireEvent.click(screen.getByRole("tab", { name: /Matrices cuantitativas/ }));
  fireEvent.click(screen.getByRole("switch", { name: /Distinguir dirección/ }));
  expect(updated.decisionModel.adjacencyMatrices[0]?.entries).toEqual([
    { fromStationId: "a", toStationId: "b", value: "8" },
  ]);
});

test("REL values can populate both directions of a quantitative matrix", () => {
  const draft = draftWithDecisionMatrices();
  draft.decisionModel.relCloseness![0]!.level = "A";
  draft.decisionModel.adjacencyMatrices[0]!.directed = true;
  draft.decisionModel.adjacencyMatrices[0]!.entries = [
    { fromStationId: "a", toStationId: "b", value: "1" },
    { fromStationId: "b", toStationId: "a", value: "2" },
  ];
  let updated = draft;
  render(<RelationsStep draft={draft} onChange={(value) => { updated = value; }} />);
  fireEvent.change(screen.getByLabelText("Nivel A"), { target: { value: "125" } });
  fireEvent.click(screen.getByRole("button", { name: "Aplicar valores a la matriz" }));
  expect(updated.decisionModel.adjacencyMatrices[0]?.entries.map((entry) => entry.value)).toEqual(["125", "125"]);
});

test("minimized REL mappings require a finite worst-value fallback", () => {
  const draft = draftWithDecisionMatrices();
  draft.decisionModel.adjacencyMatrices[0]!.direction = "minimize";
  let updated = draft;
  render(<RelationsStep draft={draft} onChange={(value) => { updated = value; }} />);
  fireEvent.change(screen.getByLabelText("Nivel A"), { target: { value: "25" } });
  fireEvent.change(screen.getByLabelText(/Valor para niveles sin asignar/), { target: { value: "20" } });
  fireEvent.click(screen.getByRole("button", { name: "Aplicar valores a la matriz" }));
  expect(screen.getByText(/debe ser mayor que todos/)).toBeTruthy();
  expect(updated.decisionModel.adjacencyMatrices[0]?.entries[0]?.value).toBe("0");
  fireEvent.change(screen.getByLabelText(/Valor para niveles sin asignar/), { target: { value: "100" } });
  fireEvent.click(screen.getByRole("button", { name: "Aplicar valores a la matriz" }));
  expect(updated.decisionModel.adjacencyMatrices[0]?.entries[0]?.value).toBe("100");
});

test("matrix cells support multiple selection and bulk updates", () => {
  const draft = draftWithDecisionMatrices();
  draft.decisionModel.undesiredPrescribedAdjacencies = [{
    firstStationId: "a", secondStationId: "b", cause: "safety",
    explanation: "Separar", provenance: "norma", policy: "warn",
  }];
  let updated = draft;
  const view = render(<RelationsStep draft={draft} onChange={(value) => { updated = value; }} />);
  const relCell = screen.getByRole("button", { name: "A, B" });
  fireEvent.click(relCell);
  expect(relCell.getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(relCell);
  expect(relCell.getAttribute("aria-pressed")).toBe("false");
  fireEvent.click(relCell);
  fireEvent.change(screen.getByLabelText("Prioridad de cercanía"), { target: { value: "E" } });
  fireEvent.change(screen.getByLabelText("Motivo operativo"), { target: { value: "Operación" } });
  fireEvent.click(screen.getByRole("button", { name: "Aplicar a campos seleccionados" }));
  expect(updated.decisionModel.relCloseness?.[0]).toMatchObject({ level: "E", reason: "Operación" });
  expect(updated.decisionModel.undesiredPrescribedAdjacencies).toEqual([]);

  view.rerender(<RelationsStep draft={updated} onChange={(value) => { updated = value; }} />);
  fireEvent.click(screen.getByRole("tab", { name: /Matrices cuantitativas/ }));
  const quantitativeCell = screen.getByRole("button", { name: "A, B" });
  fireEvent.keyDown(quantitativeCell, { key: " " });
  expect(quantitativeCell.getAttribute("aria-pressed")).toBe("true");
  fireEvent.change(screen.getByLabelText("Valor"), { target: { value: "17.5" } });
  fireEvent.click(screen.getByRole("button", { name: "Aplicar a campos seleccionados" }));
  expect(updated.decisionModel.adjacencyMatrices[0]?.entries[0]?.value).toBe("17.5");
});

test("review separates scope, criteria, matrices and execution", () => {
  const draft = draftWithDecisionMatrices();
  render(<ReviewStep draft={draft} estimate={12} validated busy={false} error={null} template={false} onTemplateChange={() => undefined} onExecute={() => undefined} />);

  expect(screen.getByRole("heading", { name: "Matriz REL" })).toBeTruthy();
  expect(screen.getByRole("region", { name: "Criterios de comparación" })).toBeTruthy();
  expect(screen.getByRole("region", { name: "Matrices cuantitativas" })).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Preparar el experimento" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Preparar y ejecutar" })).toBeTruthy();
});
