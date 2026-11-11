import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "vitest";
import type { SingleRowFacilityLayoutDraft, SingleRowFacilityLayoutDraftV2, SingleRowFacilityLayoutDraftV21 } from "@domain-ui-sdk";
import { DraftOriginKind } from "@srfl-ui/model/editor-state.types";
import { fromScientificDraft, toScientificDraft } from "@srfl-ui/model/mappers";

test("scientific definitions preserve content but receive a new internal study identity", () => {
  const source = JSON.parse(readFileSync(path.resolve(__dirname, "../../../examples/domains/single-row-facility-layout/comparison.json"), "utf8")) as SingleRowFacilityLayoutDraft;
  const editor = fromScientificDraft(source, DraftOriginKind.ImportedFile, "Importada");
  const mapped = toScientificDraft(editor);
  expect(mapped.study.id).toMatch(/^study-[0-9a-f-]{36}$/);
  expect(mapped.study.id).not.toBe(source.study.id);
  expect(mapped.schema_version).toBe("2.0.0");
  expect(mapped.domain.version).toBe("2.0.0");
  expect(mapped.study.title).toBe(source.study.title);
  expect(mapped.decision_model.retained_compatible_layouts).toBe(true);
});

test("a historical v2 flow becomes one editable matrix without losing its values", () => {
  const source = JSON.parse(readFileSync(path.resolve(__dirname, "../../../examples/domains/single-row-facility-layout/v2-complete.json"), "utf8")) as SingleRowFacilityLayoutDraftV2;
  const historical = structuredClone(source);
  historical.decision_model.adjacency_flow = {
    unit: "viajes", horizon: "turno", provenance: "ERP", directed: false,
    entries: [
      { from_station_id: "a", to_station_id: "b", quantity: "12" },
      { from_station_id: "a", to_station_id: "c", quantity: "0" },
      { from_station_id: "b", to_station_id: "c", quantity: "4" },
    ],
  };
  const editor = fromScientificDraft(historical, DraftOriginKind.ImportedFile, "Histórica");
  expect(editor.decisionModel.adjacencyMatrices).toHaveLength(1);
  expect(editor.decisionModel.adjacencyMatrices[0]?.entries[0]?.value).toBe("12");
  expect(Array.isArray(toScientificDraft(editor).decision_model.adjacency_flow)).toBe(true);
});

test("the visual station order survives serialization without changing identities", () => {
  const source = JSON.parse(readFileSync(path.resolve(__dirname, "../../../examples/domains/single-row-facility-layout/v2-complete.json"), "utf8")) as SingleRowFacilityLayoutDraftV2;
  const editor = fromScientificDraft(source, DraftOriginKind.ImportedFile, "Ordenada");
  editor.study.stationDisplayOrder = [...editor.study.stationDisplayOrder].reverse();
  const mapped = toScientificDraft(editor);
  expect(mapped.study.stations.map((station) => station.id)).toEqual(source.study.stations.map((station) => station.id).reverse());
  expect(new Set(mapped.study.stations.map((station) => station.id))).toEqual(new Set(source.study.stations.map((station) => station.id)));
});

test("SRFL 2.1 preserves its version and persisted execution mode through the editor", () => {
  const source = JSON.parse(readFileSync(path.resolve(__dirname, "../../../examples/domains/single-row-facility-layout/v2-complete.json"), "utf8")) as SingleRowFacilityLayoutDraftV2;
  const v21 = { ...source, schema_version: "2.1.0", domain: { id: "single-row-facility-layout", version: "2.1.0" }, execution: { ...source.execution, mode: "high_performance" } } as unknown as SingleRowFacilityLayoutDraftV21;
  const editor = fromScientificDraft(v21, DraftOriginKind.ImportedFile, "2.1 rápida");
  const mapped = toScientificDraft(editor);
  expect(mapped.schema_version).toBe("2.1.0");
  expect(mapped.domain.version).toBe("2.1.0");
  expect((mapped as SingleRowFacilityLayoutDraftV21).execution.mode).toBe("high_performance");
});
