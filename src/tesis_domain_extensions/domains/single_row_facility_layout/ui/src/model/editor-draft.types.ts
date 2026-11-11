import type { Attachment, EvidenceValue, ExecutionConfig, ExecutionConfigV21 } from "@domain-ui-sdk";
import type { DraftOriginKind } from "./editor-state.types";

export type EditableEntity = { clientKey: string; id: string; idManuallyEdited: boolean };
export type EditableStation = EditableEntity & { name: string };
export type EditableEvidence = { description?: string; attachments?: Attachment[]; descriptionEdited?: boolean; removedInheritedAttachments?: string[] };
export type EditableComponent = EditableEntity & EditableEvidence & { stationIds: string[] };
export type EditableDesign = EditableEntity & EditableEvidence & { title: string; baseComponentIds: string[] };
export type RelLevel = "A" | "E" | "I" | "O" | "U" | "X";
export type UndesiredCause = "safety" | "cross_contamination" | "noise" | "temperature" | "privacy" | "interference" | "process";
export type RelRequirementDraft = { firstStationId: string; secondStationId: string; level: RelLevel; reason: string; provenance: string };
export type AdjacencyValueEntryDraft = { fromStationId: string; toStationId: string; value: string };
export type AdjacencyValueMatrixDraft = {
  id: string;
  name: string;
  description: string;
  direction: "maximize" | "minimize";
  unit: string;
  referencePeriod: string;
  provenance: string;
  directed: boolean;
  entries: AdjacencyValueEntryDraft[];
};
export type DecisionModelDraft = {
  selectedObjectives: { id: string; version: "1" }[];
  retainedCompatibleLayouts: boolean;
  relCloseness: RelRequirementDraft[] | null;
  adjacencyMatrices: AdjacencyValueMatrixDraft[];
  undesiredPrescribedAdjacencies: { firstStationId: string; secondStationId: string; cause: UndesiredCause | ""; explanation: string; provenance: string; policy: "forbidden" | "warn" }[];
};

export type SrflEditorDraft = {
  schemaVersion: "2.0.0" | "2.1.0";
  domain: { id: "single-row-facility-layout"; version: "2.0.0" | "2.1.0" };
  origin: { kind: DraftOriginKind; label: string };
  templateEvidence?: { importAttachments: boolean; importRestrictionDescriptions: boolean; inherited: Record<string, EvidenceValue> };
  study: EditableEvidence & {
    id: string;
    title: string;
    description: string;
    stations: EditableStation[];
    stationDisplayOrder: string[];
    components: EditableComponent[];
    designs: EditableDesign[];
  };
  execution: ExecutionConfig | ExecutionConfigV21;
  decisionModel: DecisionModelDraft;
  reporting: { invalid_combinations: "summary" | "full" };
};
