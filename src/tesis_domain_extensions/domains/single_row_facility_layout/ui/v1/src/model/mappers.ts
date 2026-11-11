import { effectiveEvidence, initializeTemplateEvidence, STUDY_OWNER } from "./evidence";
import type { SingleRowFacilityLayoutDraft } from "@domain-ui-sdk";
import { DraftOriginKind } from "./editor-state.types";
import type { SrflEditorDraft } from "./editor-draft.types";
import { newStudyIdentifier, nextClientKey } from "./identifiers";

export function fromScientificDraft(config: SingleRowFacilityLayoutDraft, kind: DraftOriginKind, label: string): SrflEditorDraft {
  const draft: SrflEditorDraft = {
    schemaVersion: config.schema_version,
    domain: { ...config.domain }, origin: { kind, label },
    study: {
      id: newStudyIdentifier(), title: config.study.title, description: config.study.description ?? "", attachments: structuredClone(config.study.attachments ?? []),
      stations: config.study.stations.map((item) => ({ clientKey: nextClientKey("station"), id: item.id, idManuallyEdited: true, name: item.name })),
      components: config.study.components.map((item) => ({ clientKey: nextClientKey("component"), id: item.id, idManuallyEdited: true, stationIds: [...item.station_ids], utility: item.utility, description: item.description ?? "", attachments: structuredClone(item.attachments ?? []) })),
      designs: config.study.designs.map((item) => ({ clientKey: nextClientKey("design"), id: item.id, idManuallyEdited: true, title: item.title, baseComponentIds: [...item.base_component_ids], description: item.description ?? "", attachments: structuredClone(item.attachments ?? []) })),
    },
    execution: structuredClone(config.execution), reporting: { ...config.reporting },
  };
  return kind === DraftOriginKind.Template ? initializeTemplateEvidence(draft) : draft;
}

export function toScientificDraft(draft: SrflEditorDraft): SingleRowFacilityLayoutDraft {
  const documentation = (key: string) => {
    const value = effectiveEvidence(draft, key);
    return { ...(value.description.trim() ? { description: value.description.trim() } : {}), ...(value.attachments.length ? { attachments: value.attachments } : {}) };
  };
  return {
    schema_version: draft.schemaVersion, domain: draft.domain,
    study: {
      id: draft.study.id, title: draft.study.title,
      ...documentation(STUDY_OWNER),
      stations: draft.study.stations.map(({ id, name }) => ({ id, name })) as SingleRowFacilityLayoutDraft["study"]["stations"],
      components: draft.study.components.map(({ id, stationIds, utility, clientKey }) => ({ id, station_ids: stationIds, utility, ...documentation(clientKey) })) as SingleRowFacilityLayoutDraft["study"]["components"],
      designs: draft.study.designs.map(({ id, title, baseComponentIds, clientKey }) => ({ id, title, base_component_ids: baseComponentIds, ...documentation(clientKey) })) as SingleRowFacilityLayoutDraft["study"]["designs"],
    },
    execution: structuredClone(draft.execution), reporting: { ...draft.reporting },
  };
}

export function isSrflDefinition(value: unknown): value is SingleRowFacilityLayoutDraft {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as { domain?: { id?: unknown }; study?: unknown };
  return candidate.domain?.id === "single-row-facility-layout" && typeof candidate.study === "object" && candidate.study !== null;
}
