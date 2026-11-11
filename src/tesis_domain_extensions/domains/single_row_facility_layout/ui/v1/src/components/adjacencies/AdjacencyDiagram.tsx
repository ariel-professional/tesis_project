import type { EditableComponent, EditableStation } from "../../model/editor-draft.types";
import { useDiagramPositions } from "../../hooks/useDiagramPositions";

export function AdjacencyDiagram({ stations, components, selectedPath, onToggleStation, onSelectComponents }: { stations: readonly EditableStation[]; components: readonly EditableComponent[]; selectedPath: readonly string[]; onToggleStation: (id: string) => void; onSelectComponents?: (keys: string[]) => void }) {
  const ids = stations.map((item) => item.id);
  const { positions, move } = useDiagramPositions(ids);
  const edges = components.flatMap((component) => component.stationIds.slice(1).map((id, index) => ({ from: component.stationIds[index]!, to: id, id: `${component.clientKey}-${index}` })));
  return <div className="srfl-diagram"><svg viewBox="0 0 600 440" role="img" aria-label="Diagrama interactivo de adyacencias">
    {edges.map((edge) => { const from = positions[edge.from]; const to = positions[edge.to]; return from !== undefined && to !== undefined ? <line key={edge.id} x1={from.x} y1={from.y} x2={to.x} y2={to.y} className="srfl-diagram__edge" role="button" tabIndex={0} aria-label={`Ver restricciones ${edge.from} a ${edge.to}`} onClick={() => onSelectComponents?.(components.filter((item) => item.stationIds.some((station, index) => index > 0 && [station, item.stationIds[index - 1]].sort().join("|") === [edge.from, edge.to].sort().join("|"))).map((item) => item.clientKey))} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); event.currentTarget.dispatchEvent(new MouseEvent("click", { bubbles: true })); } }} /> : null; })}
    {stations.map((station) => { const point = positions[station.id]; if (point === undefined) return null; const selected = selectedPath.includes(station.id); return <g key={station.clientKey} transform={`translate(${point.x} ${point.y})`} className={`srfl-diagram__node ${selected ? "is-selected" : ""}`} onClick={() => onToggleStation(station.id)} onPointerMove={(event) => { if (event.buttons !== 1) return; const rect = event.currentTarget.ownerSVGElement?.getBoundingClientRect(); if (rect !== undefined) move(station.id, { x: ((event.clientX - rect.left) / rect.width) * 600, y: ((event.clientY - rect.top) / rect.height) * 440 }); }}><circle r="31" /><text textAnchor="middle" dy="4">{station.id.slice(0, 8)}</text></g>; })}
  </svg><p>Hacé clic en estaciones para formar un camino. Arrastralas para ordenar la vista.</p></div>;
}

