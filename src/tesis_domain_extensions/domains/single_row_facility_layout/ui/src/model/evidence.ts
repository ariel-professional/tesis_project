import type { Attachment, EvidenceUpdate, EvidenceValue } from "@domain-ui-sdk";
import type { EditableEvidence, SrflEditorDraft } from "./editor-draft.types";

export const STUDY_OWNER = "study";
export const evidenceKey = (item: Attachment) => item.kind === "file" ? `file:${item.sha256}` : `link:${item.url}`;
export function evidenceOwner(draft: SrflEditorDraft, key: string): EditableEvidence | undefined {
  return key === STUDY_OWNER ? draft.study : [...draft.study.components, ...draft.study.designs].find((item) => item.clientKey === key);
}
export function effectiveEvidence(draft: SrflEditorDraft, key: string): EvidenceValue {
  const own = evidenceOwner(draft, key);
  if (!own) return { description: "", attachments: [] };
  const inherited = draft.templateEvidence?.inherited[key];
  const isRestriction = draft.study.components.some((item) => item.clientKey === key);
  const description = !own.descriptionEdited && inherited && isRestriction
    ? draft.templateEvidence?.importRestrictionDescriptions ? inherited.description : ""
    : own.description ?? "";
  const included = draft.templateEvidence?.importAttachments ? inherited?.attachments ?? [] : [];
  const attachments = new Map(included.filter((item) => !(own.removedInheritedAttachments ?? []).includes(evidenceKey(item))).map((item) => [evidenceKey(item), item]));
  for (const item of own.attachments ?? []) attachments.set(evidenceKey(item), item);
  return { description, attachments: [...attachments.values()] };
}
export function updateEvidence(draft: SrflEditorDraft, key: string, update: EvidenceUpdate): SrflEditorDraft {
  const own = evidenceOwner(draft, key);
  if (!own) return draft;
  const before = effectiveEvidence(draft, key);
  const next = update(before);
  const inherited = draft.templateEvidence?.inherited[key]?.attachments ?? [];
  const remaining = new Set(next.attachments.map(evidenceKey));
  const removed = new Set(own.removedInheritedAttachments ?? []);
  for (const item of before.attachments) if (!remaining.has(evidenceKey(item))) removed.add(evidenceKey(item));
  const inheritedKeys = new Set(inherited.map(evidenceKey));
  const ownKeys = new Set((own.attachments ?? []).map(evidenceKey));
  const updated = { ...own,
    description: next.description,
    descriptionEdited: own.descriptionEdited || next.description !== before.description,
    attachments: next.attachments.filter((item) => !inheritedKeys.has(evidenceKey(item)) || ownKeys.has(evidenceKey(item)) || !before.attachments.some((old) => evidenceKey(old) === evidenceKey(item))),
    removedInheritedAttachments: [...removed],
  };
  return { ...draft, study: {
    ...draft.study,
    ...(key === STUDY_OWNER ? updated : {}),
    components: draft.study.components.map((item) => item.clientKey === key ? { ...item, ...updated } : item),
    designs: draft.study.designs.map((item) => item.clientKey === key ? { ...item, ...updated } : item),
  } };
}

export function initializeTemplateEvidence(draft: SrflEditorDraft): SrflEditorDraft {
  const inherited: Record<string, EvidenceValue> = {};
  for (const key of [STUDY_OWNER, ...draft.study.components.map((item) => item.clientKey), ...draft.study.designs.map((item) => item.clientKey)]) inherited[key] = effectiveEvidence(draft, key);
  return { ...draft, templateEvidence: { importAttachments: false, importRestrictionDescriptions: false, inherited }, study: {
    ...draft.study, attachments: [],
    components: draft.study.components.map((item) => ({ ...item, description: "", attachments: [] })),
    designs: draft.study.designs.map((item) => ({ ...item, attachments: [] })),
  } };
}
