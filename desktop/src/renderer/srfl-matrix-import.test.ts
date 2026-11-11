import { describe, expect, test } from "vitest";
import { parseQuantitativeMatrix, parseRelImport, parseStationNames, readDelimited } from "@srfl-ui/model/matrix-import";
import { stationAliases } from "@srfl-ui/model/station-aliases";

const stations = [
  { clientKey: "poultry", id: "poultry", idManuallyEdited: true, name: "Poultry" },
  { clientKey: "pasta", id: "pasta", idManuallyEdited: true, name: "Pasta" },
  { clientKey: "fish", id: "fish", idManuallyEdited: true, name: "Fish" },
];
const aliases = stationAliases(stations);
const imports = stations.map((station) => ({ clientKey: station.clientKey, id: station.id, alias: aliases.get(station.clientKey)! }));

test("station import reads only matrix axes or REL edge endpoints", () => {
  expect(parseStationNames(";Poultry;Fish\nPoultry;anything;-2\nFish;U;—")).toEqual(["Poultry", "Fish"]);
  expect(parseStationNames("alias_1;alias_2;nivel_rel;motivo_operativo;fuente\nPoultry;Fish;X;;\nFish;Pasta;U;;")).toEqual(["Poultry", "Fish", "Pasta"]);
  expect(() => parseStationNames(";A;A\nA;0;0\nA;0;0")).toThrow(/únicas/);
});

test("quantitative matrix accepts signed values and imported full station names", () => {
  const named = imports.map((item) => ({ ...item, name: stations.find((station) => station.id === item.id)!.name }));
  const parsed = parseQuantitativeMatrix(";Poultry;Pasta;Fish\nPoultry;—;-2;0\nPasta;-2;—;1\nFish;0;1;—", named);
  expect(parsed.entries.some((entry) => entry.value === "-2")).toBe(true);
});

describe("station aliases", () => {
  test("uses the shortest case-sensitive unique prefix", () => {
    expect(Object.fromEntries(aliases)).toEqual({ poultry: "Po", pasta: "Pa", fish: "F" });
  });

  test("adds stable numeric suffixes to identical names", () => {
    const duplicated = stationAliases([
      { clientKey: "b", id: "b", idManuallyEdited: true, name: "Área" },
      { clientKey: "a", id: "a", idManuallyEdited: true, name: "Área" },
    ]);
    expect(duplicated.get("a")).toBe("Á1");
    expect(duplicated.get("b")).toBe("Á2");
  });
});

describe("matrix imports", () => {
  test("parses quoted fields, escaped quotes and CRLF", () => {
    expect(readDelimited('\uFEFFa;b\r\n"uno;dos";"dice ""sí"""')).toEqual([["a", "b"], ["uno;dos", 'dice "sí"']]);
  });

  test("imports a partial REL list by alias and rejects inverse duplicates", () => {
    expect(parseRelImport("alias_1;alias_2;nivel_rel;motivo_operativo;fuente\nPo;F;A;;", imports)).toMatchObject({ kind: "rel-list", rows: [{ firstStationId: "fish", secondStationId: "poultry", level: "A" }] });
    expect(() => parseRelImport("alias_1;alias_2;nivel_rel;motivo_operativo;fuente\nPo;F;A;;\nF;Po;E;;", imports)).toThrow(/duplicada/);
  });

  test("imports triangular REL matrices and preserves header order", () => {
    const result = parseRelImport(";F;Po;Pa\nF;—;A;E\nPo;;—;I\nPa;;;—", imports);
    expect(result.kind).toBe("rel-matrix");
    if (result.kind === "rel-matrix") expect(result.stationDisplayOrder).toEqual(["fish", "poultry", "pasta"]);
  });

  test("detects symmetric and directed quantitative matrices", () => {
    const symmetric = parseQuantitativeMatrix(";F;Po;Pa\nF;—;1;2,0\nPo;1.0;—;3\nPa;2;3;—", imports);
    expect(symmetric.directed).toBe(false);
    expect(symmetric.entries).toHaveLength(3);
    const directed = parseQuantitativeMatrix(";F;Po;Pa\nF;—;1;2\nPo;4;—;3\nPa;2;3;—", imports);
    expect(directed.directed).toBe(true);
    expect(directed.entries).toHaveLength(6);
  });

  test("rejects incomplete matrices without returning a partial result", () => {
    expect(() => parseQuantitativeMatrix(";F;Po;Pa\nF;—;1;2\nPo;1;—;\nPa;2;3;—", imports)).toThrow(/decimal válido/);
  });
});
