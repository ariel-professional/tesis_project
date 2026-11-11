import { Button, ButtonVariant, DependencyConfirmationModal, EntityTable } from "@domain-ui-kit";
import { useState } from "react";
import type { SrflEditorDraft } from "../../model/editor-draft.types";
import { nextClientKey, slugify, uniqueIdentifier } from "../../model/identifiers";

export function StationTable({ draft, onChange }: { draft: SrflEditorDraft; onChange: (draft: SrflEditorDraft) => void }) {
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const add = () => {
    if (draft.study.stations.length >= draft.execution.integer_limits.max_n) return;
    const id = uniqueIdentifier(`estacion-${draft.study.stations.length + 1}`, draft.study.stations.map((item) => item.id));
    onChange({ ...draft, study: { ...draft.study, stations: [...draft.study.stations, { clientKey: nextClientKey("station"), id, idManuallyEdited: false, name: `Estación ${draft.study.stations.length + 1}` }] } });
  };
  const update = (clientKey: string, values: { name?: string; id?: string }) => {
    const previous = draft.study.stations.find((station) => station.clientKey === clientKey); if (previous === undefined) return;
    const stations = draft.study.stations.map((station) => {
    if (station.clientKey !== clientKey) return station;
    if (values.id !== undefined) return { ...station, id: slugify(values.id, station.id), idManuallyEdited: true };
    const name = values.name ?? station.name;
    const used = draft.study.stations.filter((item) => item.clientKey !== clientKey).map((item) => item.id);
    return { ...station, name, id: station.idManuallyEdited ? station.id : uniqueIdentifier(slugify(name, "estacion"), used) };
    });
    const current = stations.find((station) => station.clientKey === clientKey)!;
    onChange({ ...draft, study: { ...draft.study, stations, components: draft.study.components.map((component) => ({ ...component, stationIds: component.stationIds.map((id) => id === previous.id ? current.id : id) })) } });
  };
  const remove = (clientKey: string) => {
    const station = draft.study.stations.find((item) => item.clientKey === clientKey); if (station === undefined) return;
    const affectedComponents = draft.study.components.filter((item) => item.stationIds.includes(station.id));
    const removedIds = new Set(affectedComponents.map((item) => item.id));
    onChange({ ...draft, study: { ...draft.study, stations: draft.study.stations.filter((item) => item.clientKey !== clientKey), components: draft.study.components.filter((item) => !removedIds.has(item.id)), designs: draft.study.designs.map((design) => ({ ...design, baseComponentIds: design.baseComponentIds.filter((id) => !removedIds.has(id)) })) } });
    setPendingDelete(null);
  };
  const target = draft.study.stations.find((item) => item.clientKey === pendingDelete);
  const dependencies = target === undefined ? [] : draft.study.components.filter((item) => item.stationIds.includes(target.id)).map((item) => `Restricción ${item.id}`);
  return <><div className="srfl-toolbar"><p>{draft.study.stations.length} de {draft.execution.integer_limits.max_n} estaciones</p><Button onClick={add} disabled={draft.study.stations.length >= draft.execution.integer_limits.max_n}>Agregar estación</Button></div>
    <EntityTable headers={["Nombre", "ID", "Acciones"]} empty={draft.study.stations.length === 0}>{draft.study.stations.map((station) => <tr key={station.clientKey}><td><input className="ui-input" value={station.name} onChange={(event) => update(station.clientKey, { name: event.target.value })} /></td><td><input className="ui-input" value={station.id} onChange={(event) => update(station.clientKey, { id: event.target.value })} /></td><td><Button variant={ButtonVariant.Ghost} onClick={() => setPendingDelete(station.clientKey)}>Eliminar</Button></td></tr>)}</EntityTable>
    {target !== undefined && <DependencyConfirmationModal title={`Eliminar ${target.name}`} dependencies={dependencies.length > 0 ? dependencies : ["No hay referencias dependientes."]} onClose={() => setPendingDelete(null)} onConfirm={() => remove(target.clientKey)} />}</>;
}
