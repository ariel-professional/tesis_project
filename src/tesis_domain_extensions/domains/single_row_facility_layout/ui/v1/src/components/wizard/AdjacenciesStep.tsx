import { Button, DependencyConfirmationModal, NumberField, Panel } from "@domain-ui-kit";
import { useState } from "react";
import type { SrflEditorDraft } from "../../model/editor-draft.types";
import { nextClientKey, slugify, uniqueIdentifier } from "../../model/identifiers";
import { AdjacencyDiagram } from "../adjacencies/AdjacencyDiagram";
import { AdjacencyTable } from "../adjacencies/AdjacencyTable";

export function AdjacenciesStep({ draft, onChange }: { draft: SrflEditorDraft; onChange: (draft: SrflEditorDraft) => void }) {
  const [selectedKeys, setSelectedKeys] = useState<readonly string[]>([]);
  const [path, setPath] = useState<string[]>([]); const [utility, setUtility] = useState(1); const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const toggle = (id: string) => setPath((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const add = () => {
    if (path.length < 2) return;
    const base = path.join("-"); const id = uniqueIdentifier(base, draft.study.components.map((item) => item.id));
    onChange({ ...draft, study: { ...draft.study, components: [...draft.study.components, { clientKey: nextClientKey("component"), id, idManuallyEdited: false, stationIds: path, utility }] } }); setPath([]); setUtility(1); setSelectedKeys([]);
  };
  const remove = (clientKey: string) => { const item = draft.study.components.find((component) => component.clientKey === clientKey); if (item === undefined) return; onChange({ ...draft, study: { ...draft.study, components: draft.study.components.filter((component) => component.clientKey !== clientKey), designs: draft.study.designs.map((design) => ({ ...design, baseComponentIds: design.baseComponentIds.filter((id) => id !== item.id) })) } }); setPendingDelete(null); };
  const update = (clientKey: string, values: { id?: string; utility?: number }) => {
    const previous = draft.study.components.find((item) => item.clientKey === clientKey); if (previous === undefined) return;
    const nextId = values.id === undefined ? previous.id : slugify(values.id, previous.id);
    onChange({ ...draft, study: { ...draft.study, components: draft.study.components.map((item) => item.clientKey === clientKey ? { ...item, id: nextId, idManuallyEdited: values.id !== undefined || item.idManuallyEdited, utility: values.utility ?? item.utility } : item), designs: draft.study.designs.map((design) => ({ ...design, baseComponentIds: design.baseComponentIds.map((id) => id === previous.id ? nextId : id) })) } });
  };
  const target = draft.study.components.find((item) => item.clientKey === pendingDelete);
  const dependencies = target === undefined ? [] : draft.study.designs.filter((design) => design.baseComponentIds.includes(target.id)).map((design) => `Diseño ${design.title}`);
  return <section className="srfl-step">
    <div className="srfl-step__intro"><h2>Restricciones</h2><p>Seleccioná dos estaciones para un par o más estaciones para un camino compuesto.</p></div>
    <div className="srfl-restrictions-layout">
      <section className="srfl-restrictions-list" aria-label="Lista de restricciones">
        <h3>Restricciones agregadas · {draft.study.components.length}</h3>
        <AdjacencyTable expanded={selectedKeys} onExpandedChange={setSelectedKeys} draft={draft} onChange={update} onDelete={setPendingDelete} />
      </section>
      <aside className="srfl-restrictions-tools" aria-label="Agregar restricciones">
        <Panel className="srfl-path-builder">
          <h3>Nueva restricción</h3>
          <div className="srfl-path-preview">{path.length === 0 ? "Seleccioná estaciones en el diagrama" : path.join(" → ")}</div>
          <NumberField label="Utilidad" min={0} value={utility} onChange={(event) => setUtility(Number(event.target.value))} />
          <Button disabled={path.length < 2} onClick={add}>Agregar restricción</Button>
        </Panel>
        <AdjacencyDiagram stations={draft.study.stations} components={draft.study.components} selectedPath={path} onToggleStation={toggle} onSelectComponents={setSelectedKeys} />
      </aside>
    </div>
    {target !== undefined && <DependencyConfirmationModal title={`Eliminar ${target.id}`} dependencies={dependencies.length > 0 ? dependencies : ["No hay diseños dependientes."]} onClose={() => setPendingDelete(null)} onConfirm={() => remove(target.clientKey)} />}
  </section>;
}
