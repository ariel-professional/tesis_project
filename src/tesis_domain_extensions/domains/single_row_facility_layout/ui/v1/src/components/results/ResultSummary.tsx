import { DocumentationPanel } from "../evidence/DocumentationPanel";
import {
  Button,
  ButtonVariant,
  Card,
  ActionIconButton,
  MetricCard,
  PageHeader,
  StatusBadge,
  SwitchField,
} from "@domain-ui-kit";
import type { AttachmentService, SingleRowFacilityLayoutDraft, LayoutCaseResult, SingleRowFacilityLayoutResult } from "@domain-ui-sdk";
import { useEffect, useState } from "react";
import { CaseDetail } from "./CaseDetail";
import { DesignComparison } from "./DesignComparison";

function display(value: unknown): string {
  if (value === null || value === undefined) return "Inconcluso";
  if (typeof value === "object" && value !== null && "value" in value)
    return String((value as { value: unknown }).value ?? "Inconcluso");
  return String(value);
}
export function ResultSummary({
  result,
  service,
  onHome,
  template,
  templateBusy,
  onTemplateChange,
}: {
  result: SingleRowFacilityLayoutResult;
  service?: AttachmentService;
  onHome: () => void;
  template?: boolean;
  templateBusy?: boolean;
  onTemplateChange?: (enabled: boolean) => void;
}) {
  const [documentation, setDocumentation] = useState<SingleRowFacilityLayoutDraft | null>(null);
  const [documentationError, setDocumentationError] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    setDocumentation(null); setDocumentationError(null);
    void service?.documentation(result.execution.domain_experiment_id).then((config) => { if (current) setDocumentation(config as SingleRowFacilityLayoutDraft); }).catch((reason: unknown) => { if (current) setDocumentationError(String(reason)); });
    return () => { current = false; };
  }, [service, result.execution.domain_experiment_id]);
  const [designId, setDesignId] = useState(result.designs[0]?.design_id ?? "");
  const [selectedCase, setSelectedCase] = useState<LayoutCaseResult | null>(null);
  const design =
    result.designs.find((item) => item.design_id === designId) ??
    result.designs[0];
  return (
    <main className="srfl-page">
      <PageHeader
        eyebrow="SRFL 1.0.0 · resultado confirmado"
        title={result.study_title}
        description={result.study_description ?? "Comparación de alternativas y frontera de Pareto por diseño."}
        actions={
          <Button variant={ButtonVariant.Secondary} onClick={onHome}>
            Volver al inicio
          </Button>
        }
      />
      {onTemplateChange !== undefined && <Card><SwitchField label="Guardar como plantilla" description="Permite crear un experimento nuevo con esta misma configuración." checked={template ?? false} disabled={templateBusy} onChange={onTemplateChange} /></Card>}
      {documentation && <DocumentationPanel config={documentation} service={service} />}
      {documentationError && <p role="alert">No se pudieron cargar los antecedentes: {documentationError}</p>}
      <div className="srfl-metrics">
        <MetricCard
          label="Combinaciones teóricas"
          value={display(result.generation.theoretical_combinations)}
        />
        <MetricCard
          label="Selecciones válidas"
          value={display(result.generation.valid_selections)}
        />
        <MetricCard
          label="Inválidas"
          value={display(result.generation.invalid_combinations)}
        />
        <MetricCard
          label="Casos CORE"
          value={display(result.generation.core_cases)}
        />
      </div>
      <div className="srfl-design-tabs">
        {result.designs.map((item) => (
          <button
            type="button"
            key={item.design_id}
            className={item.design_id === designId ? "is-active" : ""}
            onClick={() => setDesignId(item.design_id)}
          >
            {item.design_title}
            <StatusBadge tone="info">
              {item.pareto_case_ids.length} Pareto
            </StatusBadge>
          </button>
        ))}
      </div>
      {design !== undefined && (
        <Card>
          <h2>{design.design_title}</h2>
          <div className="srfl-comparison-bar">
            <span
              style={{
                width: `${Math.max(6, Math.min(100, Number(design.valid_case_count) || 0))}%`,
              }}
            />
          </div>
          <p>
            {display(design.valid_case_count)} casos válidos ·{" "}
            {display(design.invalid_combination_count)} combinaciones inválidas.
          </p>
          <div className="srfl-result-split"><div className="ui-table-wrap">
            <table className="ui-table">
              <thead>
                <tr>
                  <th>Componentes</th>
                  <th>Utilidad</th>
                  <th>Disposiciones</th>
                  <th><span className="sr-only">Acciones</span></th>
                </tr>
              </thead>
              <tbody>
                {design.cases
                  .filter((item) => item.pareto_optimal)
                  .map((item) => (
                    <tr key={item.case_id}>
                      <td>{item.component_ids.join(", ")}</td>
                      <td>{display(item.total_utility)}</td>
                      <td>{display(item.compatible_layout_count)}</td>
                      <td><ActionIconButton action="view-details" label="Ver detalle del caso" className="srfl-case-options" onClick={() => setSelectedCase(item)} /></td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div><DesignComparison cases={design.cases} onSelect={setSelectedCase} /></div>
          <details className="srfl-result-details">
            <summary>Ver todos los casos y estructuras</summary>
            {design.cases.map((item) => (
              <article key={item.case_id}>
                <strong>{item.case_id.slice(0, 12)}</strong>
                <p>
                  {item.forest_structure.paths
                    .map((path) => path.join(" → "))
                    .join(" · ") || "Sin caminos"}
                </p>
                <small>
                  Estaciones aisladas:{" "}
                  {item.forest_structure.isolated_station_ids.join(", ") ||
                    "ninguna"}
                </small>
              </article>
            ))}
          </details>
        </Card>
      )}
      {selectedCase !== null && <CaseDetail documentation={documentation ?? undefined} service={service} item={selectedCase} stations={result.stations} onClose={() => setSelectedCase(null)} />}
    </main>
  );
}
