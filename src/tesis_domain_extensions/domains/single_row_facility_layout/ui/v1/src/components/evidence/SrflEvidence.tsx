import { createContext, useContext, useRef, useState, type ReactNode } from "react";
import { EvidenceEditor } from "@domain-ui-kit";
import type { AttachmentService, EvidenceUpdate } from "@domain-ui-sdk";
import type { SrflEditorDraft } from "../../model/editor-draft.types";
import { effectiveEvidence, updateEvidence } from "../../model/evidence";

type EvidenceContextValue = {
  draft: SrflEditorDraft; service?: AttachmentService; pending: number;
  change: (owner: string, update: EvidenceUpdate) => void; busy: (delta: number) => void;
};
const Context = createContext<EvidenceContextValue | null>(null);
export function SrflEvidenceProvider({ draft, onChange, service, children }: { draft: SrflEditorDraft; onChange: (draft: SrflEditorDraft) => void; service?: AttachmentService; children: ReactNode }) {
  const [pending, setPending] = useState(0);
  const current = useRef(draft); current.current = draft;
  const change = (owner: string, update: EvidenceUpdate) => {
    const next = updateEvidence(current.current, owner, update);
    if (next === current.current) return;
    current.current = next; onChange(next);
  };
  return <Context.Provider value={{ draft, service, pending, change, busy: (delta) => setPending((count) => Math.max(0, count + delta)) }}>{children}</Context.Provider>;
}
export const useEvidenceActivity = () => useContext(Context)?.pending ?? 0;
export function SrflEvidenceField({ owner, label = "Descripción", readOnly = false, fallback }: { owner: string; label?: string; readOnly?: boolean; fallback?: { draft: SrflEditorDraft; onChange: (draft: SrflEditorDraft) => void } }) {
  const context = useContext(Context);
  if (!context) return fallback ? <EvidenceEditor value={effectiveEvidence(fallback.draft, owner)} label={label} onChange={(update) => fallback.onChange(updateEvidence(fallback.draft, owner, update))} /> : null;
  return <EvidenceEditor value={effectiveEvidence(context.draft, owner)} label={label} readOnly={readOnly} service={context.service} onBusy={context.busy} onChange={(update) => context.change(owner, update)} />;
}
