import { effectiveEvidence, initializeTemplateEvidence, STUDY_OWNER } from "./evidence";
import type { SingleRowFacilityLayoutDraft, SingleRowFacilityLayoutDraftV2, SingleRowFacilityLayoutDraftV21 } from "@domain-ui-sdk";
import { DraftOriginKind } from "./editor-state.types";
import type { DecisionModelDraft, SrflEditorDraft, UndesiredCause } from "./editor-draft.types";
import { newStudyIdentifier, nextClientKey } from "./identifiers";
import { normalizeMatrixEntries } from "./matrix-pairs";
import { orderedStations } from "./station-aliases";

type SingleRowFacilityDraftInput = SingleRowFacilityLayoutDraft | SingleRowFacilityLayoutDraftV2 | SingleRowFacilityLayoutDraftV21;
type RawAdjacencyMatrix = { id: string; name: string; description: string; direction: "maximize" | "minimize"; unit: string; reference_period?: string | null; provenance: string; directed: boolean; entries: { from_station_id: string; to_station_id: string; value: string | number }[] };

function decisionModelFromConfig(config: SingleRowFacilityDraftInput): DecisionModelDraft {
  if (!("decision_model" in config)) return { selectedObjectives: [{ id: "retained-compatible-layouts", version: "1" }], retainedCompatibleLayouts: true, relCloseness: null, adjacencyMatrices: [], undesiredPrescribedAdjacencies: [] };
  const rawFlow = config.decision_model.adjacency_flow;
  const adjacencyMatrices = rawFlow === null || rawFlow === undefined
    ? []
    : Array.isArray(rawFlow)
      ? (rawFlow as RawAdjacencyMatrix[]).map((matrix) => ({
          id: matrix.id, name: matrix.name, description: matrix.description,
          direction: matrix.direction, unit: matrix.unit,
          referencePeriod: matrix.reference_period ?? "", provenance: matrix.provenance,
          directed: matrix.directed,
          entries: normalizeMatrixEntries(matrix.entries.map((item) => ({ fromStationId: item.from_station_id, toStationId: item.to_station_id, value: String(item.value) })), matrix.directed),
        }))
      : [{
          id: "movimientos", name: "Movimientos entre áreas",
          description: "Cantidad de movimientos atendidos entre áreas que deben quedar adyacentes.",
          direction: "maximize" as const, unit: rawFlow.unit,
          referencePeriod: rawFlow.horizon, provenance: rawFlow.provenance,
          directed: rawFlow.directed,
          entries: normalizeMatrixEntries(rawFlow.entries.map((item) => ({ fromStationId: item.from_station_id, toStationId: item.to_station_id, value: String(item.quantity) })), rawFlow.directed),
        }];
  return {
    selectedObjectives: (config.decision_model.selected_objectives ?? []).map((item) => ({ id: item.id, version: item.version })),
    retainedCompatibleLayouts: config.decision_model.retained_compatible_layouts ?? false,
    relCloseness: config.decision_model.rel_closeness?.requirements.map((item) => ({ firstStationId: item.first_station_id, secondStationId: item.second_station_id, level: item.level, reason: item.reason, provenance: item.provenance })) ?? null,
    adjacencyMatrices,
    undesiredPrescribedAdjacencies: (config.decision_model.undesired_prescribed_adjacencies ?? []).map((item) => ({ firstStationId: item.first_station_id, secondStationId: item.second_station_id, cause: item.cause, explanation: item.explanation, provenance: item.provenance, policy: item.policy })),
  };
}

export function fromScientificDraft(config: SingleRowFacilityDraftInput, kind: DraftOriginKind, label: string): SrflEditorDraft {
  const isV2 = "decision_model" in config;
  const stations = config.study.stations.map((item) => ({ clientKey: nextClientKey("station"), id: item.id, idManuallyEdited: true, name: item.name }));
  const draft: SrflEditorDraft = {
    schemaVersion: config.schema_version === "2.1.0" ? "2.1.0" : "2.0.0",
    domain: { id: "single-row-facility-layout", version: config.schema_version === "2.1.0" ? "2.1.0" : "2.0.0" }, origin: { kind, label },
    study: {
      id: newStudyIdentifier(), title: config.study.title, description: config.study.description ?? "", attachments: structuredClone(config.study.attachments ?? []),
      stations,
      stationDisplayOrder: stations.map((station) => station.clientKey),
      components: config.study.components.map((item) => ({ clientKey: nextClientKey("component"), id: item.id, idManuallyEdited: true, stationIds: [...item.station_ids], description: item.description ?? "", attachments: structuredClone(item.attachments ?? []) })),
      designs: config.study.designs.map((item) => ({ clientKey: nextClientKey("design"), id: item.id, idManuallyEdited: true, title: item.title, baseComponentIds: [...item.base_component_ids], description: item.description ?? "", attachments: structuredClone(item.attachments ?? []) })),
    },
    execution: structuredClone(config.execution), decisionModel: decisionModelFromConfig(config), reporting: isV2 ? { invalid_combinations: config.reporting?.invalid_combinations ?? "summary" } : { invalid_combinations: config.reporting.invalid_combinations },
  };
  return kind === DraftOriginKind.Template ? initializeTemplateEvidence(draft) : draft;
}

export function toScientificDraft(draft: SrflEditorDraft): SingleRowFacilityLayoutDraftV2 | SingleRowFacilityLayoutDraftV21 {
  const documentation = (key: string) => {
    const value = effectiveEvidence(draft, key);
    return { ...(value.description.trim() ? { description: value.description.trim() } : {}), ...(value.attachments.length ? { attachments: value.attachments } : {}) };
  };
  const payload = {
    schema_version: draft.schemaVersion, domain: { id: "single-row-facility-layout", version: draft.schemaVersion },
    study: {
      id: draft.study.id, title: draft.study.title,
      ...documentation(STUDY_OWNER),
      stations: orderedStations(draft.study.stations, draft.study.stationDisplayOrder).map(({ id, name }) => ({ id, name })) as SingleRowFacilityLayoutDraftV2["study"]["stations"],
      components: draft.study.components.map(({ id, stationIds, clientKey }) => ({ id, station_ids: stationIds, ...documentation(clientKey) })) as SingleRowFacilityLayoutDraftV2["study"]["components"],
      designs: draft.study.designs.map(({ id, title, baseComponentIds, clientKey }) => ({ id, title, base_component_ids: baseComponentIds, ...documentation(clientKey) })) as SingleRowFacilityLayoutDraftV2["study"]["designs"],
    },
    execution: structuredClone(draft.execution), decision_model: {
      selected_objectives: draft.decisionModel.selectedObjectives,
      retained_compatible_layouts: draft.decisionModel.retainedCompatibleLayouts,
      rel_closeness: draft.decisionModel.relCloseness === null ? undefined : ({ requirements: draft.decisionModel.relCloseness.map((item) => ({ first_station_id: item.firstStationId, second_station_id: item.secondStationId, level: item.level, reason: item.reason, provenance: item.provenance })) } as unknown as SingleRowFacilityLayoutDraftV2["decision_model"]["rel_closeness"]),
      adjacency_flow: draft.decisionModel.adjacencyMatrices.length === 0 ? undefined : (draft.decisionModel.adjacencyMatrices.map((matrix) => ({
        id: matrix.id, name: matrix.name, description: matrix.description,
        direction: matrix.direction, unit: matrix.unit,
        ...(matrix.referencePeriod.trim() ? { reference_period: matrix.referencePeriod.trim() } : {}),
        provenance: matrix.provenance, directed: matrix.directed,
        entries: normalizeMatrixEntries(matrix.entries, matrix.directed).map((item) => ({ from_station_id: item.fromStationId, to_station_id: item.toStationId, value: item.value })),
      })) as unknown as SingleRowFacilityLayoutDraftV2["decision_model"]["adjacency_flow"]),
      undesired_prescribed_adjacencies: draft.decisionModel.undesiredPrescribedAdjacencies.map((item) => ({ first_station_id: item.firstStationId, second_station_id: item.secondStationId, cause: item.cause as UndesiredCause, explanation: item.explanation, provenance: item.provenance, policy: item.policy })),
    }, reporting: structuredClone(draft.reporting),
  } as unknown as SingleRowFacilityLayoutDraftV2;
  if (draft.schemaVersion === "2.1.0") return {
    ...payload,
    execution: {
      ...payload.execution,
      mode: (draft.execution as import("@domain-ui-sdk").ExecutionConfigV21).mode ?? "standard",
    },
  } as unknown as SingleRowFacilityLayoutDraftV21;
  return payload;
}

export function isSrflDefinition(value: unknown): value is SingleRowFacilityLayoutDraft {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as { domain?: { id?: unknown }; study?: unknown };
  return candidate.domain?.id === "single-row-facility-layout" && typeof candidate.study === "object" && candidate.study !== null;
}
