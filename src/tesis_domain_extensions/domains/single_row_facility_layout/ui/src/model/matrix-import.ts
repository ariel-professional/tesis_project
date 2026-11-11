import type { AdjacencyValueEntryDraft, RelLevel, RelRequirementDraft } from "./editor-draft.types";
import { canonicalPair, canonicalPairKey } from "./matrix-pairs";

export type ImportStation = { clientKey: string; id: string; alias: string; name?: string };
export type RelListImport = { kind: "rel-list"; rows: { firstStationId: string; secondStationId: string; level: RelLevel; reason: string; provenance: string }[] };
export type RelMatrixImport = { kind: "rel-matrix"; levels: Map<string, RelLevel>; stationDisplayOrder: string[] };
export type QuantitativeMatrixImport = { directed: boolean; entries: AdjacencyValueEntryDraft[]; stationDisplayOrder: string[] };

export class MatrixImportError extends Error {}

const relLevels = new Set<RelLevel>(["A", "E", "I", "O", "U", "X"]);
const listHeader = ["alias_1", "alias_2", "nivel_rel", "motivo_operativo", "fuente"];

export function parseStationNames(raw: string): string[] {
  const rows = readDelimited(raw);
  if (rows[0]?.map((value) => value.toLowerCase()).join("\0") === listHeader.join("\0")) {
    const names = new Set<string>();
    rows.slice(1).forEach((row, index) => {
      if (row.length !== 5 || !row[0]?.trim() || !row[1]?.trim()) throw new MatrixImportError(`Fila ${index + 2}: se esperan cinco columnas y dos estaciones.`);
      names.add(row[0].trim()); names.add(row[1].trim());
    });
    if (names.size === 0) throw new MatrixImportError("La lista no contiene estaciones.");
    return [...names];
  }
  if (rows[0]?.[0] !== "") throw new MatrixImportError("La primera celda de una matriz debe estar vacía.");
  const names = rows[0].slice(1).map((value) => value.trim());
  if (names.length === 0 || names.some((value) => !value) || new Set(names).size !== names.length) throw new MatrixImportError("Los encabezados deben contener estaciones únicas y no vacías.");
  if (rows.length !== names.length + 1) throw new MatrixImportError("La matriz debe contener una fila por estación.");
  rows.slice(1).forEach((row, index) => {
    if (row.length > names.length + 1 || row[0]?.trim() !== names[index]) throw new MatrixImportError(`Fila ${index + 2}: la estación de la primera columna no coincide con el encabezado.`);
  });
  return names;
}

function parseDelimited(raw: string, delimiter: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = []; let field = ""; let quoted = false;
  const text = raw.replace(/^\uFEFF/, "");
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') { field += '"'; index += 1; }
      else if (character === '"') quoted = false;
      else field += character;
    } else if (character === '"' && field.length === 0) quoted = true;
    else if (character === delimiter) { row.push(field.trim()); field = ""; }
    else if (character === "\n" || character === "\r") {
      if (character === "\r" && text[index + 1] === "\n") index += 1;
      row.push(field.trim()); field = "";
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
    } else field += character;
  }
  if (quoted) throw new MatrixImportError("Hay un campo entrecomillado sin cerrar.");
  row.push(field.trim());
  if (row.some((value) => value !== "")) rows.push(row);
  return rows;
}

export function readDelimited(raw: string): string[][] {
  for (const delimiter of [";", "\t", ","]) {
    const rows = parseDelimited(raw, delimiter);
    if ((rows[0]?.length ?? 0) > 1) return rows;
  }
  throw new MatrixImportError("No se pudo detectar el separador. Usá punto y coma, coma o tabulación.");
}

function aliasLookup(stations: readonly ImportStation[]) {
  const result = new Map<string, ImportStation>();
  for (const station of stations) {
    if (result.has(station.alias)) throw new MatrixImportError(`El alias ${station.alias} no es único.`);
    result.set(station.alias, station);
    if (station.name && station.name !== station.alias) {
      const existing = result.get(station.name);
      if (existing && existing.clientKey !== station.clientKey) throw new MatrixImportError(`El nombre ${station.name} es ambiguo.`);
      result.set(station.name, station);
    }
  }
  return result;
}

function stationFor(alias: string, lookup: Map<string, ImportStation>, row: number, column: number) {
  const station = lookup.get(alias.trim());
  if (station === undefined) throw new MatrixImportError(`Fila ${row}, columna ${column}: alias desconocido «${alias}».`);
  return station;
}

function normalizedDecimal(raw: string, row: number, column: number): string {
  const value = raw.trim().replace(",", ".");
  if (!/^-?\d+(?:\.\d+)?$/.test(value)) throw new MatrixImportError(`Fila ${row}, columna ${column}: ingresá un decimal válido.`);
  const negative = value.startsWith("-");
  const [integer = "0", fraction = ""] = (negative ? value.slice(1) : value).split(".");
  const normalizedInteger = integer.replace(/^0+(?=\d)/, "");
  const normalizedFraction = fraction.replace(/0+$/, "");
  const normalized = normalizedFraction ? `${normalizedInteger}.${normalizedFraction}` : normalizedInteger;
  return negative && normalized !== "0" ? `-${normalized}` : normalized;
}

function isDiagonalPlaceholder(value: string, row: number, column: number) {
  const trimmed = value.trim();
  return trimmed === "" || trimmed === "-" || trimmed === "—" || normalizedDecimal(trimmed, row, column) === "0";
}

function matrixAxes(rows: string[][], stations: readonly ImportStation[]) {
  if (rows.length === 0 || rows[0]?.[0]?.trim() !== "") throw new MatrixImportError("La primera celda de una matriz debe estar vacía.");
  const lookup = aliasLookup(stations);
  const header = rows[0]!.slice(1);
  if (header.length !== stations.length) throw new MatrixImportError("La fila de encabezado debe contener todos los alias exactamente una vez.");
  const headerStations = header.map((alias, index) => stationFor(alias, lookup, 1, index + 2));
  if (new Set(headerStations.map((station) => station.clientKey)).size !== stations.length) throw new MatrixImportError("La fila de encabezado contiene alias repetidos.");
  if (rows.length !== stations.length + 1) throw new MatrixImportError("La matriz debe contener una fila por estación.");
  rows.slice(1).forEach((row, index) => {
    if (row.length > header.length + 1) throw new MatrixImportError(`Fila ${index + 2}: hay columnas adicionales.`);
    const station = stationFor(row[0] ?? "", lookup, index + 2, 1);
    if (station.clientKey !== headerStations[index]?.clientKey) throw new MatrixImportError(`Fila ${index + 2}: el alias de la primera columna no coincide con el encabezado.`);
  });
  return { headerStations, order: headerStations.map((station) => station.clientKey) };
}

export function parseRelImport(raw: string, stations: readonly ImportStation[]): RelListImport | RelMatrixImport {
  const rows = readDelimited(raw);
  if (rows[0]?.map((value) => value.toLowerCase()).join("\0") === listHeader.join("\0")) {
    const lookup = aliasLookup(stations); const seen = new Set<string>();
    const imported = rows.slice(1).map((row, index) => {
      if (row.length !== 5) throw new MatrixImportError(`Fila ${index + 2}: se esperaban cinco columnas.`);
      const first = stationFor(row[0] ?? "", lookup, index + 2, 1);
      const second = stationFor(row[1] ?? "", lookup, index + 2, 2);
      if (first.id === second.id) throw new MatrixImportError(`Fila ${index + 2}: no se admiten relaciones reflexivas.`);
      const key = canonicalPairKey(first.id, second.id);
      if (seen.has(key)) throw new MatrixImportError(`Fila ${index + 2}: la relación está duplicada, incluso en sentido inverso.`);
      seen.add(key);
      const level = row[2] as RelLevel;
      if (!relLevels.has(level)) throw new MatrixImportError(`Fila ${index + 2}, columna 3: nivel REL inválido.`);
      const [firstStationId, secondStationId] = canonicalPair(first.id, second.id);
      return { firstStationId, secondStationId, level, reason: row[3] ?? "", provenance: row[4] ?? "" };
    });
    return { kind: "rel-list", rows: imported };
  }
  const { headerStations, order } = matrixAxes(rows, stations);
  const levels = new Map<string, RelLevel>();
  for (let left = 0; left < headerStations.length; left += 1) {
    const diagonal = rows[left + 1]?.[left + 1] ?? "";
    if (!isDiagonalPlaceholder(diagonal, left + 2, left + 2)) throw new MatrixImportError(`Fila ${left + 2}, columna ${left + 2}: la diagonal debe quedar vacía, en cero o con guion.`);
    for (let right = left + 1; right < headerStations.length; right += 1) {
      const forward = rows[left + 1]?.[right + 1]?.trim() ?? "";
      const reverse = rows[right + 1]?.[left + 1]?.trim() ?? "";
      if (!forward && !reverse) throw new MatrixImportError(`Falta el nivel REL para ${headerStations[left]!.alias}–${headerStations[right]!.alias}.`);
      if (forward && !relLevels.has(forward as RelLevel)) throw new MatrixImportError(`Nivel REL inválido para ${headerStations[left]!.alias}–${headerStations[right]!.alias}.`);
      if (reverse && !relLevels.has(reverse as RelLevel)) throw new MatrixImportError(`Nivel REL inválido para ${headerStations[right]!.alias}–${headerStations[left]!.alias}.`);
      if (forward && reverse && forward !== reverse) throw new MatrixImportError(`Los dos sentidos de ${headerStations[left]!.alias}–${headerStations[right]!.alias} se contradicen.`);
      levels.set(canonicalPairKey(headerStations[left]!.id, headerStations[right]!.id), (forward || reverse) as RelLevel);
    }
  }
  return { kind: "rel-matrix", levels, stationDisplayOrder: order };
}

export function parseQuantitativeMatrix(raw: string, stations: readonly ImportStation[]): QuantitativeMatrixImport {
  const rows = readDelimited(raw);
  const { headerStations, order } = matrixAxes(rows, stations);
  const values = new Map<string, string>(); let directed = false;
  for (let row = 0; row < headerStations.length; row += 1) {
    for (let column = 0; column < headerStations.length; column += 1) {
      const rawValue = rows[row + 1]?.[column + 1] ?? "";
      if (row === column) {
        if (!isDiagonalPlaceholder(rawValue, row + 2, column + 2)) throw new MatrixImportError(`Fila ${row + 2}, columna ${column + 2}: la diagonal debe quedar vacía, en cero o con guion.`);
      } else values.set(`${row}\0${column}`, normalizedDecimal(rawValue, row + 2, column + 2));
    }
  }
  for (let left = 0; left < headerStations.length; left += 1) for (let right = left + 1; right < headerStations.length; right += 1) {
    if (values.get(`${left}\0${right}`) !== values.get(`${right}\0${left}`)) directed = true;
  }
  const entries: AdjacencyValueEntryDraft[] = [];
  if (directed) {
    for (let row = 0; row < headerStations.length; row += 1) for (let column = 0; column < headerStations.length; column += 1) if (row !== column) entries.push({ fromStationId: headerStations[row]!.id, toStationId: headerStations[column]!.id, value: values.get(`${row}\0${column}`)! });
  } else {
    for (let left = 0; left < headerStations.length; left += 1) for (let right = left + 1; right < headerStations.length; right += 1) {
      const [fromStationId, toStationId] = canonicalPair(headerStations[left]!.id, headerStations[right]!.id);
      entries.push({ fromStationId, toStationId, value: values.get(`${left}\0${right}`)! });
    }
  }
  return { directed, entries, stationDisplayOrder: order };
}

function csvField(value: string) { return /[;"\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value; }
export function relListExample(stations: readonly ImportStation[], rel: readonly RelRequirementDraft[]) {
  const aliasById = new Map(stations.map((station) => [station.id, station.alias]));
  return [listHeader.join(";"), ...rel.map((item) => [aliasById.get(item.firstStationId) ?? item.firstStationId, aliasById.get(item.secondStationId) ?? item.secondStationId, item.level, item.reason, item.provenance].map(csvField).join(";"))].join("\n");
}
export function matrixExample(stations: readonly ImportStation[], value: (fromId: string, toId: string) => string) {
  return [["", ...stations.map((station) => station.alias)].join(";"), ...stations.map((row) => [row.alias, ...stations.map((column) => row.id === column.id ? "—" : value(row.id, column.id))].map(csvField).join(";"))].join("\n");
}
