import type { EditableStation, SrflEditorDraft } from "./editor-draft.types";
import { buildMatrixEntries, canonicalPairKey, directedPairKey } from "./matrix-pairs";

const pairKey = canonicalPairKey;

export function reconcileRelationsForStations(
  draft: SrflEditorDraft,
  stations: readonly EditableStation[],
): SrflEditorDraft["decisionModel"] {
  const renamed = new Map<string, string>();
  for (const station of stations) {
    const previous = draft.study.stations.find(
      (item) => item.clientKey === station.clientKey,
    );
    if (previous !== undefined) renamed.set(previous.id, station.id);
  }
  const translate = (id: string) => renamed.get(id) ?? id;
  const ids = stations.map((item) => item.id).sort();
  const oldRel = new Map(
    (draft.decisionModel.relCloseness ?? []).map((item) => [
      pairKey(translate(item.firstStationId), translate(item.secondStationId)),
      item,
    ]),
  );
  const relCloseness =
    draft.decisionModel.relCloseness === null
      ? null
      : ids.flatMap((first, index) =>
          ids.slice(index + 1).map((second) => {
            const previous = oldRel.get(pairKey(first, second));
            return previous === undefined
              ? {
                  firstStationId: first,
                  secondStationId: second,
                  level: "U" as const,
                  reason: "",
                  provenance: "",
                }
              : { ...previous, firstStationId: first, secondStationId: second };
          }),
        );
  const adjacencyMatrices = draft.decisionModel.adjacencyMatrices.map((matrix) => {
    const previousValues = new Map(
      matrix.entries.map((item) => [
        `${translate(item.fromStationId)}\0${translate(item.toStationId)}`,
        item.value,
      ]),
    );
    const entries = buildMatrixEntries(ids, matrix.directed, (from, to) =>
      previousValues.get(directedPairKey(from, to))
      ?? (!matrix.directed ? previousValues.get(directedPairKey(to, from)) : undefined)
      ?? "0");
    return { ...matrix, entries };
  });
  const xPairs = new Set(
    (relCloseness ?? [])
      .filter((item) => item.level === "X")
      .map((item) => pairKey(item.firstStationId, item.secondStationId)),
  );
  return {
    ...draft.decisionModel,
    relCloseness,
    adjacencyMatrices,
    undesiredPrescribedAdjacencies:
      draft.decisionModel.undesiredPrescribedAdjacencies
        .map((item) => ({
          ...item,
          firstStationId: translate(item.firstStationId),
          secondStationId: translate(item.secondStationId),
        }))
        .filter((item) =>
          xPairs.has(pairKey(item.firstStationId, item.secondStationId)),
        ),
  };
}
