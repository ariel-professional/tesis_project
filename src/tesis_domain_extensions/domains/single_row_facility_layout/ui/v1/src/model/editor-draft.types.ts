import type { Attachment, EvidenceValue, ExecutionConfig, LayoutReporting } from "@domain-ui-sdk";
import type { DraftOriginKind } from "./editor-state.types";

export type EditableEntity = { clientKey: string; id: string; idManuallyEdited: boolean };
export type EditableStation = EditableEntity & { name: string };
export type EditableEvidence = { description?: string; attachments?: Attachment[]; descriptionEdited?: boolean; removedInheritedAttachments?: string[] };
export type EditableComponent = EditableEntity & EditableEvidence & { stationIds: string[]; utility: number };
export type EditableDesign = EditableEntity & EditableEvidence & { title: string; baseComponentIds: string[] };

export type SrflEditorDraft = {
  schemaVersion: "1.0.0";
  domain: { id: "single-row-facility-layout"; version: "1.0.0" };
  origin: { kind: DraftOriginKind; label: string };
  templateEvidence?: { importAttachments: boolean; importRestrictionDescriptions: boolean; inherited: Record<string, EvidenceValue> };
  study: EditableEvidence & {
    id: string;
    title: string;
    description: string;
    stations: EditableStation[];
    components: EditableComponent[];
    designs: EditableDesign[];
  };
  execution: ExecutionConfig;
  reporting: LayoutReporting;
};
