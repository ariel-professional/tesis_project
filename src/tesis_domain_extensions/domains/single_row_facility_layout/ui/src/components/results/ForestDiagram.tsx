import type { LayoutCaseResultV2, StationV2 } from "@domain-ui-sdk";

type SelectedEdge = readonly [string, string];
const edgeKey = ([first, second]: SelectedEdge) => [first, second].sort().join("\0");

export function ForestDiagram({ item, stations, selectedEdge, onSelectEdge }: { item: LayoutCaseResultV2; stations: readonly StationV2[]; selectedEdge?: SelectedEdge | null; onSelectEdge?: (edge: SelectedEdge) => void }) {
  const names = new Map(stations.map((station) => [station.id, station.name]));
  const rows = [...item.forest_structure.paths, ...item.forest_structure.isolated_station_ids.map((id) => [id])];
  return <div className="srfl-case-diagram" role={onSelectEdge === undefined ? "img" : "group"} aria-label="Bosque de restricciones y adyacencias del caso">
    {rows.map((path, row) => <div key={`${row}-${path.join("-")}`} className="srfl-case-path">
      {path.map((id, index) => {
        const next = path[index + 1];
        const edge: SelectedEdge | null = next === undefined ? null : [id, next];
        const selected = edge !== null && selectedEdge != null && edgeKey(edge) === edgeKey(selectedEdge);
        return <span key={`${id}-${index}`}><span className="srfl-case-node" title={id}>{names.get(id) ?? id}</span>{edge !== null && (onSelectEdge === undefined ? <span className="srfl-case-edge" aria-hidden="true" /> : <button type="button" className={`srfl-case-edge srfl-case-edge--interactive${selected ? " is-selected" : ""}`} aria-label={`Ver detalle de ${names.get(edge[0]) ?? edge[0]} y ${names.get(edge[1]) ?? edge[1]}`} aria-pressed={selected} onClick={() => onSelectEdge(edge)}><span className="sr-only">Ver detalle de la arista</span></button>)}</span>;
      })}
    </div>)}
  </div>;
}
