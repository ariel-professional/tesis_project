import { DocumentationPanel } from "../evidence/DocumentationPanel";
import { Modal } from "@domain-ui-kit";
import type { AttachmentService, SingleRowFacilityLayoutDraft, LayoutCaseResult, Station } from "@domain-ui-sdk";

function display(value: unknown): string {
  if (value === null || value === undefined) return "Inconcluso";
  if (typeof value === "object" && "value" in value) return String((value as { value: unknown }).value ?? "Inconcluso");
  return String(value);
}

function ForestDiagram({ item, stations }: { item: LayoutCaseResult; stations: readonly Station[] }) {
  const names = new Map(stations.map((station) => [station.id, station.name]));
  const rows = [...item.forest_structure.paths, ...item.forest_structure.isolated_station_ids.map((id) => [id])];
  return <div className="srfl-case-diagram" role="img" aria-label="Bosque de restricciones del caso">{rows.map((path, row) => <div key={`${row}-${path.join("-")}`} className="srfl-case-path">{path.map((id, index) => <span key={`${id}-${index}`}><span className="srfl-case-node" title={id}>{names.get(id) ?? id}</span>{index < path.length - 1 && <span className="srfl-case-edge" aria-hidden="true" />}</span>)}</div>)}</div>;
}

export function CaseDetail({ item, stations, onClose, documentation, service }: { item: LayoutCaseResult; stations: readonly Station[]; onClose: () => void; documentation?: SingleRowFacilityLayoutDraft; service?: AttachmentService }) {
  return <Modal title="Detalle del caso" onClose={onClose}>
    {documentation && <DocumentationPanel config={documentation} service={service} componentIds={item.component_ids} designId={item.design_id} />}
    <ForestDiagram item={item} stations={stations} />
    <dl className="srfl-case-details">
      <dt>Referencia del caso</dt><dd><code>{item.case_id}</code></dd>
      <dt>Run CORE</dt><dd><code>{item.core_run_id}</code></dd>
      <dt>Factibilidad</dt><dd>{item.feasibility}</dd>
      <dt>Utilidad total</dt><dd>{display(item.total_utility)}</dd>
      <dt>Layouts compatibles</dt><dd>{display(item.compatible_layout_count)}</dd>
      <dt>Componentes</dt><dd>{item.component_ids.join(", ") || "Ninguno"}</dd>
      <dt>Componentes agregados</dt><dd>{item.added_component_ids.join(", ") || "Ninguno"}</dd>
      <dt>Aristas prescriptas</dt><dd>{item.prescribed_edge_count}</dd>
      <dt>Óptimo de Pareto</dt><dd>{item.pareto_optimal ? "Sí" : "No"}</dd>
    </dl>
    {item.diagnostics.length > 0 && <section><h3>Diagnósticos</h3><ul>{item.diagnostics.map((entry) => <li key={`${entry.core_code}-${entry.message}`}>{entry.message} <code>{entry.core_code}</code></li>)}</ul></section>}
    {item.limitations.length > 0 && <section><h3>Limitaciones</h3><ul>{item.limitations.map((entry) => <li key={`${entry.code}-${entry.message}`}>{entry.message}</li>)}</ul></section>}
    <p className="srfl-note">El gráfico representa restricciones de adyacencia, no una disposición física final.</p>
  </Modal>;
}
