import { effectiveEvidence } from "../../model/evidence";
import { Button } from "@domain-ui-kit";
import type { SrflEditorDraft } from "../../model/editor-draft.types";
import { nextClientKey, uniqueIdentifier } from "../../model/identifiers";
import { DesignCard } from "../designs/DesignCard";

export function DesignsStep({ draft, onChange }: { draft: SrflEditorDraft; onChange: (draft: SrflEditorDraft) => void }) {
  const update = (clientKey: string, design: SrflEditorDraft["study"]["designs"][number]) => onChange({ ...draft, study: { ...draft.study, designs: draft.study.designs.map((item) => item.clientKey === clientKey ? design : item) } });
  const add = () => { const id = uniqueIdentifier(`diseno-${draft.study.designs.length + 1}`, draft.study.designs.map((item) => item.id)); onChange({ ...draft, study: { ...draft.study, designs: [...draft.study.designs, { clientKey: nextClientKey("design"), id, idManuallyEdited: false, title: `Diseño ${draft.study.designs.length + 1}`, baseComponentIds: [] }] } }); };
  const duplicate = (clientKey: string) => { const source = draft.study.designs.find((item) => item.clientKey === clientKey); if (source === undefined) return; const id = uniqueIdentifier(`${source.id}-copia`, draft.study.designs.map((item) => item.id)); onChange({ ...draft, study: { ...draft.study, designs: [...draft.study.designs, { ...structuredClone(source), ...effectiveEvidence(draft, source.clientKey), descriptionEdited: true, removedInheritedAttachments: [], clientKey: nextClientKey("design"), id, title: `${source.title} (copia)` }] } }); };
  return <section className="srfl-step"><div className="srfl-step__intro srfl-toolbar"><div><h2>Diseños</h2><p>Creá alternativas indicando qué requisitos son obligatorios en cada una.</p></div><Button onClick={add}>Agregar diseño</Button></div><div className="srfl-design-grid">{draft.study.designs.map((design) => <DesignCard key={design.clientKey} design={design} components={draft.study.components} onChange={(value) => update(design.clientKey, value)} onDuplicate={() => duplicate(design.clientKey)} onDelete={() => onChange({ ...draft, study: { ...draft.study, designs: draft.study.designs.filter((item) => item.clientKey !== design.clientKey) } })} />)}</div></section>;
}
