import { effectiveEvidence } from "../../model/evidence";
import { Button, ButtonVariant, Modal, SearchableMultiSelect, SwitchField, TextField } from "@domain-ui-kit";
import { useEffect, useState } from "react";
import type { SrflEditorDraft } from "../../model/editor-draft.types";
import { nextClientKey, uniqueIdentifier } from "../../model/identifiers";
import { DesignCard } from "../designs/DesignCard";

export function DesignsStep({ draft, onChange }: { draft: SrflEditorDraft; onChange: (draft: SrflEditorDraft) => void }) {
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newBaseComponentIds, setNewBaseComponentIds] = useState<readonly string[]>([]);
  const [newControl, setNewControl] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const hasControl = draft.study.designs.some((item) => item.baseComponentIds.length === 0);
  useEffect(() => { if (notice === null) return; const timer = window.setTimeout(() => setNotice(null), 3000); return () => window.clearTimeout(timer); }, [notice]);
  const update = (clientKey: string, design: SrflEditorDraft["study"]["designs"][number]) => {
    if (design.baseComponentIds.length === 0 && draft.study.designs.some((item) => item.clientKey !== clientKey && item.baseComponentIds.length === 0)) { setNotice("Ya existe un diseño de control sin restricciones obligatorias."); return; }
    onChange({ ...draft, study: { ...draft.study, designs: draft.study.designs.map((item) => item.clientKey === clientKey ? design : item) } });
  };
  const openAdd = () => { setNewTitle(`Diseño ${draft.study.designs.length + 1}`); setNewBaseComponentIds([]); setNewControl(false); setCreating(true); };
  const add = () => {
    const id = uniqueIdentifier(`diseno-${draft.study.designs.length + 1}`, draft.study.designs.map((item) => item.id));
    onChange({ ...draft, study: { ...draft.study, designs: [...draft.study.designs, { clientKey: nextClientKey("design"), id, idManuallyEdited: false, title: newTitle.trim(), baseComponentIds: newControl ? [] : [...newBaseComponentIds] }] } });
    setCreating(false);
  };
  const duplicate = (clientKey: string) => { const source = draft.study.designs.find((item) => item.clientKey === clientKey); if (source === undefined) return; const id = uniqueIdentifier(`${source.id}-copia`, draft.study.designs.map((item) => item.id)); onChange({ ...draft, study: { ...draft.study, designs: [...draft.study.designs, { ...structuredClone(source), ...effectiveEvidence(draft, source.clientKey), descriptionEdited: true, removedInheritedAttachments: [], clientKey: nextClientKey("design"), id, title: `${source.title} (copia)` }] } }); };
  const canCreate = newTitle.trim() !== "" && (newControl ? !hasControl : newBaseComponentIds.length > 0);
  return <section className="srfl-step"><div className="srfl-step__intro srfl-toolbar"><div><h2>Diseños</h2><p>Creá alternativas indicando qué requisitos son obligatorios en cada una. Podés incluir un único diseño de control sin restricciones.</p></div><Button onClick={openAdd}>Agregar diseño</Button></div><div className="srfl-design-grid">{draft.study.designs.map((design) => <DesignCard key={design.clientKey} design={design} components={draft.study.components} onChange={(value) => update(design.clientKey, value)} onDuplicate={() => duplicate(design.clientKey)} onDelete={() => onChange({ ...draft, study: { ...draft.study, designs: draft.study.designs.filter((item) => item.clientKey !== design.clientKey) } })} />)}</div>{creating && <Modal title="Agregar diseño" onClose={() => setCreating(false)} actions={<><Button variant={ButtonVariant.Secondary} onClick={() => setCreating(false)}>Cancelar</Button><Button disabled={!canCreate} onClick={add}>Agregar</Button></>}><div className="srfl-design-create"><TextField label="Nombre del diseño" value={newTitle} onChange={(event) => setNewTitle(event.target.value)} /><SwitchField label="Diseño de control" description={hasControl ? "Ya existe un diseño de control." : "No tendrá restricciones obligatorias y servirá como referencia."} checked={newControl} disabled={hasControl} onChange={(checked) => { setNewControl(checked); if (checked) setNewBaseComponentIds([]); }} />{!newControl && <div className="srfl-design-field"><strong>Restricciones obligatorias</strong><span>Elegí al menos una restricción para la base.</span><SearchableMultiSelect options={draft.study.components.map((item) => ({ value: item.id, label: item.stationIds.join(" → ") }))} selected={newBaseComponentIds} onChange={setNewBaseComponentIds} /></div>}</div></Modal>}{notice !== null && <div className="srfl-toast srfl-toast--notice" role="status">{notice}</div>}</section>;
}
