import type { AdjacencyValueEntryDraft } from "./editor-draft.types";

export type MatrixCell = { rowId: string; columnId: string };

export const directedPairKey = (first: string, second: string) =>
  `${first}\0${second}`;

export const canonicalPair = (
  first: string,
  second: string,
): readonly [string, string] =>
  first <= second ? [first, second] : [second, first];

export const canonicalPairKey = (first: string, second: string) =>
  directedPairKey(...canonicalPair(first, second));

export const matrixCellKey = (
  first: string,
  second: string,
  directed: boolean,
) => directed ? directedPairKey(first, second) : canonicalPairKey(first, second);

export function normalizeMatrixEntries(
  entries: readonly AdjacencyValueEntryDraft[],
  directed: boolean,
): AdjacencyValueEntryDraft[] {
  return entries.map((entry) => {
    if (directed) return { ...entry };
    const [fromStationId, toStationId] = canonicalPair(
      entry.fromStationId,
      entry.toStationId,
    );
    return { ...entry, fromStationId, toStationId };
  });
}

export function buildMatrixEntries(
  stationIds: readonly string[],
  directed: boolean,
  valueFor: (from: string, to: string) => string = () => "0",
): AdjacencyValueEntryDraft[] {
  if (directed) {
    return stationIds.flatMap((from) =>
      stationIds
        .filter((to) => to !== from)
        .map((to) => ({ fromStationId: from, toStationId: to, value: valueFor(from, to) })),
    );
  }
  return stationIds.flatMap((first, index) =>
    stationIds.slice(index + 1).map((second) => {
      const [fromStationId, toStationId] = canonicalPair(first, second);
      return {
        fromStationId,
        toStationId,
        value: valueFor(fromStationId, toStationId),
      };
    }),
  );
}
