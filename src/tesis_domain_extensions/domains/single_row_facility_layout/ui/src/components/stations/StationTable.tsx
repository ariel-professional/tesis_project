import {
  Button,
  ButtonVariant,
  DependencyConfirmationModal,
  EntityTable,
  TextAreaField,
} from "@domain-ui-kit";
import { useState } from "react";
import type { SrflEditorDraft } from "../../model/editor-draft.types";
import {
  nextClientKey,
  slugify,
  uniqueIdentifier,
} from "../../model/identifiers";
import { parseStationNames } from "../../model/matrix-import";
import { reconcileRelationsForStations } from "../../model/reconcile-relations";
import { orderedStations, stationAliases } from "../../model/station-aliases";

export function StationTable({
  draft,
  onChange,
}: {
  draft: SrflEditorDraft;
  onChange: (draft: SrflEditorDraft) => void;
}) {
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [importText, setImportText] = useState("");
  const [importError, setImportError] = useState<string | null>(null);
  const applyImport = (raw: string) => {
    try {
      const names = parseStationNames(raw);
      if (names.length > draft.execution.integer_limits.max_n) throw new Error(`El máximo configurado es ${draft.execution.integer_limits.max_n} estaciones.`);
      const oldByName = new Map(draft.study.stations.map((station) => [station.name, station]));
      const ids: string[] = draft.study.stations.filter((station) => names.includes(station.name)).map((station) => station.id);
      const stations = names.map((name) => {
        const previous = oldByName.get(name);
        const id = previous?.id ?? uniqueIdentifier(slugify(name, "estacion"), ids);
        if (previous === undefined) ids.push(id);
        return previous ?? { clientKey: nextClientKey("station"), id, idManuallyEdited: false, name };
      });
      const kept = new Set(stations.map((station) => station.id));
      const components = draft.study.components.filter((component) => component.stationIds.every((id) => kept.has(id)));
      const componentIds = new Set(components.map((component) => component.id));
      onChange({ ...draft, study: { ...draft.study, stations, components, stationDisplayOrder: stations.map((station) => station.clientKey), designs: draft.study.designs.map((design) => ({ ...design, baseComponentIds: design.baseComponentIds.filter((id) => componentIds.has(id)) })) }, decisionModel: reconcileRelationsForStations(draft, stations) });
      setImportError(null);
    } catch (error) { setImportError(error instanceof Error ? error.message : String(error)); }
  };
  const add = () => {
    if (draft.study.stations.length >= draft.execution.integer_limits.max_n)
      return;
    const id = uniqueIdentifier(
      `estacion-${draft.study.stations.length + 1}`,
      draft.study.stations.map((item) => item.id),
    );
    const clientKey = nextClientKey("station");
    const stations = [
      ...draft.study.stations,
      {
        clientKey,
        id,
        idManuallyEdited: false,
        name: `Estación ${draft.study.stations.length + 1}`,
      },
    ];
    onChange({
      ...draft,
      study: { ...draft.study, stations, stationDisplayOrder: [...orderedStations(draft.study.stations, draft.study.stationDisplayOrder).map((station) => station.clientKey), clientKey] },
      decisionModel: reconcileRelationsForStations(draft, stations),
    });
  };
  const update = (
    clientKey: string,
    values: { name?: string },
  ) => {
    const previous = draft.study.stations.find(
      (station) => station.clientKey === clientKey,
    );
    if (previous === undefined) return;
    const stations = draft.study.stations.map((station) => {
      if (station.clientKey !== clientKey) return station;
      const name = values.name ?? station.name;
      const used = draft.study.stations
        .filter((item) => item.clientKey !== clientKey)
        .map((item) => item.id);
      return {
        ...station,
        name,
        id: station.idManuallyEdited
          ? station.id
          : uniqueIdentifier(slugify(name, "estacion"), used),
      };
    });
    const current = stations.find(
      (station) => station.clientKey === clientKey,
    )!;
    onChange({
      ...draft,
      study: {
        ...draft.study,
        stations,
        components: draft.study.components.map((component) => ({
          ...component,
          stationIds: component.stationIds.map((id) =>
            id === previous.id ? current.id : id,
          ),
        })),
      },
      decisionModel: reconcileRelationsForStations(draft, stations),
    });
  };
  const remove = (clientKey: string) => {
    const station = draft.study.stations.find(
      (item) => item.clientKey === clientKey,
    );
    if (station === undefined) return;
    const affectedComponents = draft.study.components.filter((item) =>
      item.stationIds.includes(station.id),
    );
    const removedIds = new Set(affectedComponents.map((item) => item.id));
    const stations = draft.study.stations.filter(
      (item) => item.clientKey !== clientKey,
    );
    onChange({
      ...draft,
      study: {
        ...draft.study,
        stations,
        stationDisplayOrder: draft.study.stationDisplayOrder.filter((key) => key !== clientKey),
        components: draft.study.components.filter(
          (item) => !removedIds.has(item.id),
        ),
        designs: draft.study.designs.map((design) => ({
          ...design,
          baseComponentIds: design.baseComponentIds.filter(
            (id) => !removedIds.has(id),
          ),
        })),
      },
      decisionModel: reconcileRelationsForStations(draft, stations),
    });
    setPendingDelete(null);
  };
  const target = draft.study.stations.find(
    (item) => item.clientKey === pendingDelete,
  );
  const dependencies =
    target === undefined
      ? []
      : draft.study.components
          .filter((item) => item.stationIds.includes(target.id))
          .map((item) => `Restricción ${item.id}`);
  const displayedStations = orderedStations(draft.study.stations, draft.study.stationDisplayOrder);
  const aliases = stationAliases(draft.study.stations);
  return (
    <>
      <div className="srfl-toolbar">
        <p>
          {draft.study.stations.length} de{" "}
          {draft.execution.integer_limits.max_n} estaciones
        </p>
        <Button
          onClick={add}
          disabled={
            draft.study.stations.length >= draft.execution.integer_limits.max_n
          }
        >
          Agregar estación
        </Button>
      </div>
      <details className="srfl-import-panel">
        <summary>Importar estaciones</summary>
        <p>Pegá una matriz REL o cuantitativa, o una lista de aristas REL. Sólo se leen los nombres de las estaciones.</p>
        {importError && <p role="alert" className="ui-field__error">{importError}</p>}
        <TextAreaField label="Datos tabulares" value={importText} onChange={(event) => setImportText(event.target.value)} />
        <div className="srfl-button-row">
          <Button variant={ButtonVariant.Secondary} onClick={() => applyImport(importText)}>Aplicar estaciones</Button>
          <label className="ui-button ui-button--secondary">Elegir archivo CSV<input className="sr-only" type="file" accept=".csv,text/csv,text/plain" onChange={(event) => { const file = event.target.files?.[0]; if (file) void file.text().then((value) => { setImportText(value); applyImport(value); }).catch((error: unknown) => setImportError(String(error))); event.target.value = ""; }} /></label>
        </div>
      </details>
      <EntityTable
        headers={["Nombre", "ID", "Alias", "Acciones"]}
        empty={draft.study.stations.length === 0}
      >
        {displayedStations.map((station) => (
          <tr key={station.clientKey}>
            <td>
              <input
                className="ui-input"
                value={station.name}
                onChange={(event) =>
                  update(station.clientKey, { name: event.target.value })
                }
              />
            </td>
            <td>
              <input
                className="ui-input"
                value={station.id}
                readOnly
                aria-label={`ID de ${station.name}`}
              />
            </td>
            <td>
              <input
                className="ui-input"
                value={aliases.get(station.clientKey) ?? ""}
                readOnly
                aria-label={`Alias de ${station.name}`}
              />
            </td>
            <td>
              <Button
                variant={ButtonVariant.Ghost}
                onClick={() => setPendingDelete(station.clientKey)}
              >
                Eliminar
              </Button>
            </td>
          </tr>
        ))}
      </EntityTable>
      {target !== undefined && (
        <DependencyConfirmationModal
          title={`Eliminar ${target.name}`}
          dependencies={
            dependencies.length > 0
              ? dependencies
              : ["No hay referencias dependientes."]
          }
          onClose={() => setPendingDelete(null)}
          onConfirm={() => remove(target.clientKey)}
        />
      )}
    </>
  );
}
