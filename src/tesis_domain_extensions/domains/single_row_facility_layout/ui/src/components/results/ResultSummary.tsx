import {
  Button,
  ButtonVariant,
  Card,
  MetricCard,
  PageHeader,
  Panel,
  StatusBadge,
  SwitchField,
} from "@domain-ui-kit";
import type {
  AttachmentService,
  LayoutCaseResultV2,
  SingleRowFacilityLayoutDraftV2,
  SingleRowFacilityLayoutResult,
  SingleRowFacilityLayoutResultV2,
  SingleRowFacilityLayoutResultV21,
} from "@domain-ui-sdk";
import type { DomainUiHost } from "@domain-ui-sdk";
import { useEffect, useMemo, useRef, useState } from "react";
import { DocumentationPanel } from "../evidence/DocumentationPanel";
import { CaseDetail } from "./CaseDetail";
import { DesignComparison } from "./DesignComparison";
import { formatCount } from "../../model/display-values";
import { FastResultView, normalizeFastCaseDetail } from "./FastResultView";
import {
  createSrflResultSource,
  type FastResultSummaryV21,
  type SrflCaseDetail,
} from "../../model/srfl-result-source";
import { MetricsView, metricIndex } from "./MetricsView";

const display = (value: number | string | null | undefined) =>
  value == null ? "Inconcluso" : formatCount(value);
function HistoricalResult({
  result,
  onHome,
}: {
  result: SingleRowFacilityLayoutResult;
  onHome: () => void;
}) {
  return (
    <main className="srfl-page">
      <PageHeader
        eyebrow="Histórico · SRFL 1.0.0 · sólo lectura"
        title={result.study_title}
        description="Este resultado conserva utilidad y Pareto bidimensional según su contrato original. No puede editarse ni prepararse como v2."
        actions={
          <Button variant={ButtonVariant.Secondary} onClick={onHome}>
            Volver
          </Button>
        }
      />
      <div className="srfl-metrics">
        <MetricCard
          label="Combinaciones teóricas"
          value={display(result.generation.theoretical_combinations)}
        />
        <MetricCard
          label="Válidas"
          value={display(result.generation.valid_selections)}
        />
        <MetricCard
          label="Inválidas"
          value={display(result.generation.invalid_combinations)}
        />
      </div>
      {result.designs.map((design) => (
        <Card key={design.design_id}>
          <h2>{design.design_title}</h2>
          <div className="ui-table-wrap">
            <table className="ui-table">
              <thead>
                <tr>
                  <th>Caso</th>
                  <th>Disponibilidad</th>
                  <th>Restrictividad</th>
                  <th>Utilidad histórica</th>
                  <th>Pareto histórico</th>
                </tr>
              </thead>
              <tbody>
                {design.cases.map((item) => (
                  <tr key={item.case_id}>
                    <td>{item.case_id.slice(0, 12)}</td>
                    <td>
                      {item.availability_ratio
                        ? `${item.availability_ratio.numerator}/${item.availability_ratio.denominator}`
                        : "—"}
                    </td>
                    <td>
                      {item.restrictiveness_ratio
                        ? `${item.restrictiveness_ratio.numerator}/${item.restrictiveness_ratio.denominator}`
                        : "—"}
                    </td>
                    <td>{display(item.total_utility)}</td>
                    <td>
                      {item.pareto_optimal === true
                        ? "Óptimo"
                        : item.dominated === true
                          ? "Dominado"
                          : "Inconcluso"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
    </main>
  );
}
function ResultV2({
  result,
  host,
  service,
  onHome,
  template,
  templateBusy,
  onTemplateChange,
}: {
  result:
    | SingleRowFacilityLayoutResultV2
    | SingleRowFacilityLayoutResultV21
    | FastResultSummaryV21;
  host?: DomainUiHost;
  service?: AttachmentService;
  onHome: () => void;
  template?: boolean;
  templateBusy?: boolean;
  onTemplateChange?: (enabled: boolean) => void;
}) {
  const fast = "files" in result;
  const standardResult = fast
    ? undefined
    : (result as
        | SingleRowFacilityLayoutResultV2
        | SingleRowFacilityLayoutResultV21);
  const [documentation, setDocumentation] =
    useState<SingleRowFacilityLayoutDraftV2 | null>(null);
  const [documentationError, setDocumentationError] = useState<string | null>(
    null,
  );
  const [caseDetailError, setCaseDetailError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"detail" | "metrics">("detail");
  useEffect(() => {
    let current = true;
    setDocumentation(null);
    setDocumentationError(null);
    void service
      ?.documentation(String(result.execution.domain_experiment_id))
      .then((config) => {
        if (current) setDocumentation(config as SingleRowFacilityLayoutDraftV2);
      })
      .catch((reason: unknown) => {
        if (current) setDocumentationError(String(reason));
      });
    return () => {
      current = false;
    };
  }, [service, result.execution.domain_experiment_id]);
  const [designId, setDesignId] = useState(result.designs[0]?.design_id ?? "");
  const activeDesignId = useRef(designId);
  activeDesignId.current = designId;
  const resultSource = useMemo(
    () =>
      host === undefined
        ? undefined
        : createSrflResultSource(
            fast ? result : (result as SingleRowFacilityLayoutResultV2),
            String(
              (result.execution as { domain_run_id?: string }).domain_run_id ??
                "",
            ),
            host,
          ),
    [host, result],
  );
  const [selectedCase, setSelectedCase] = useState<{
    item: LayoutCaseResultV2;
    equivalents: readonly LayoutCaseResultV2[];
    dominators?: readonly LayoutCaseResultV2[];
    equivalentCount?: number;
    loading?: boolean;
  } | null>(null);
  const design =
    result.designs.find((item) => item.design_id === designId) ??
    result.designs[0];
  const standardDesign =
    standardResult?.designs.find((item) => item.design_id === designId) ??
    standardResult?.designs[0];
  const objectiveAliases = Object.fromEntries(
    result.objective_snapshots.map(({ definition }) => [
      definition.id,
      `${definition.id === "retained-compatible-layouts" ? "Flexibilidad de distribución" : definition.name} · ${definition.direction === "maximize" ? "↑ Maximizar" : "↓ Minimizar"}`,
    ]),
  );
  const objectiveDirections = Object.fromEntries(
    result.objective_snapshots.map(({ definition }) => [
      definition.id,
      definition.direction,
    ]),
  );
  const physicalAlternatives = fast
    ? String(
        BigInt(result.generation.valid_selections) -
          BigInt(result.generation.duplicate_forests),
      )
    : new Set(
        standardResult!.designs.flatMap((item) =>
          item.cases.map((caseItem) => caseItem.forest_id),
        ),
      ).size;
  const runId = String(
    (result.execution as { domain_run_id?: string }).domain_run_id ?? "",
  );
  const selectTab = (next: "detail" | "metrics") => setActiveTab(next);
  const openMetricCase = async (caseId: string) => {
    if (resultSource === undefined || design === undefined)
      throw new Error("El detalle del caso no está disponible.");
    const openedDesignId = design.design_id;
    const present = (fetched: SrflCaseDetail) => {
      if (activeDesignId.current !== openedDesignId) return;
      const detail = fast ? normalizeFastCaseDetail(fetched) : fetched;
      setSelectedCase({
        item: detail.item as LayoutCaseResultV2,
        equivalents: detail.equivalents as readonly LayoutCaseResultV2[],
        dominators: detail.dominators as readonly LayoutCaseResultV2[],
        equivalentCount: detail.equivalent_count,
        loading: detail.loading,
      });
    };
    const detail = await resultSource.caseDetail(
      openedDesignId,
      caseId,
      fast ? present : undefined,
    );
    present(detail);
  };
  return (
    <main className="srfl-page srfl-results-page">
      <PageHeader
        eyebrow={`SRFL ${result.schema_version} · resultado${fast ? " · alto rendimiento" : ""}`}
        title={result.study_title}
        description={
          result.study_description ?? "Frontera Pareto multidimensional."
        }
        actions={
          <Button variant={ButtonVariant.Secondary} onClick={onHome}>
            Volver
          </Button>
        }
      />
      <div className="srfl-design-tabs" aria-label="Diseños">
        {result.designs.map((item) => (
          <button
            type="button"
            key={item.design_id}
            className={item.design_id === designId ? "is-active" : ""}
            aria-pressed={item.design_id === designId}
            onClick={() => setDesignId(item.design_id)}
          >
            {item.design_title}
            <StatusBadge tone="info">
              {fast
                ? display(
                    (item as FastResultSummaryV21["designs"][number])
                      .pareto_case_count,
                  )
                : new Set(
                    (
                      item as SingleRowFacilityLayoutResultV2["designs"][number]
                    ).cases
                      .filter(
                        (caseItem) =>
                          caseItem.pareto_classification.pareto_optimal ===
                          true,
                      )
                      .map((caseItem) => caseItem.forest_id),
                  ).size}{" "}
              no dominadas
            </StatusBadge>
          </button>
        ))}
      </div>
      <div className="srfl-results-layout">
        <aside className="srfl-results-index">
          <div
            className="srfl-result-tablist"
            role="tablist"
            aria-label="Vistas del resultado"
            onKeyDown={(event) => {
              if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
                event.preventDefault();
                const next = activeTab === "detail" ? "metrics" : "detail";
                setActiveTab(next);
                document.getElementById(`result-tab-${next}`)?.focus();
              }
            }}
          >
            <button
              id="result-tab-detail"
              type="button"
              role="tab"
              aria-selected={activeTab === "detail"}
              aria-controls="result-panel-detail"
              tabIndex={activeTab === "detail" ? 0 : -1}
              onClick={() => selectTab("detail")}
            >
              Detalle
            </button>
            <button
              id="result-tab-metrics"
              type="button"
              role="tab"
              aria-selected={activeTab === "metrics"}
              aria-controls="result-panel-metrics"
              tabIndex={activeTab === "metrics" ? 0 : -1}
              onClick={() => selectTab("metrics")}
            >
              Métricas
            </button>
          </div>
          {activeTab === "detail" ? (
            <nav aria-label="Índice de Detalle">
              <strong>Detalle</strong>
              <a href="#resultado-resumen">Resumen general</a>
              <a href="#resultado-pareto">Casos no dominados</a>
              <a href="#resultado-grafico">Gráfico de casos</a>
              <a href="#resultado-tabla">Tabla completa</a>
            </nav>
          ) : (
            <nav aria-label="Índice de Métricas">
              <strong>Métricas</strong>
              {metricIndex.map(([id, title]) => (
                <a key={id} href={`#metric-${id}`}>
                  {title}
                </a>
              ))}
            </nav>
          )}
        </aside>
        <div className="srfl-results-content">
          {activeTab === "detail" ? (
            <section
              id="result-panel-detail"
              role="tabpanel"
              aria-labelledby="result-tab-detail"
              tabIndex={0}
            >
              <section
                id="resultado-resumen"
                className="srfl-result-anchor"
                aria-labelledby="resultado-resumen-titulo"
              >
                <h2 id="resultado-resumen-titulo" className="sr-only">
                  Resumen general
                </h2>
                {onTemplateChange !== undefined && (
                  <Panel>
                    <SwitchField
                      label="Guardar como plantilla"
                      description="Permite crear otro experimento con esta configuración."
                      checked={template ?? false}
                      disabled={templateBusy}
                      onChange={onTemplateChange}
                    />
                  </Panel>
                )}
                {documentation && (
                  <DocumentationPanel
                    config={documentation}
                    service={service}
                  />
                )}
                {documentationError && (
                  <p className="srfl-error" role="alert">
                    No se pudieron cargar los antecedentes: {documentationError}
                  </p>
                )}
                <div className="srfl-metrics">
                  <MetricCard
                    label="Combinaciones teóricas"
                    value={display(result.generation.theoretical_combinations)}
                  />
                  <MetricCard
                    label="Alternativas físicas"
                    value={display(physicalAlternatives)}
                  />
                  <MetricCard
                    label="Selecciones inválidas"
                    value={display(result.generation.invalid_combinations)}
                  />
                  <MetricCard
                    label="Selecciones equivalentes"
                    value={display(result.generation.duplicate_forests)}
                  />
                </div>
                <Panel>
                  <h2>Criterios aplicados</h2>
                  <ul>
                    {result.objective_snapshots.map((item) => (
                      <li key={item.definition.id}>
                        {objectiveAliases[item.definition.id] ??
                          item.definition.name}{" "}
                        · {item.definition.formula}
                      </li>
                    ))}
                  </ul>
                </Panel>
              </section>
              {design !== undefined && (
                <Panel>
                  <h2>{design.design_title}</h2>
                  <p>
                    {fast
                      ? `${display((design as FastResultSummaryV21["designs"][number]).valid_case_count)} casos válidos · ${display((design as FastResultSummaryV21["designs"][number]).invalid_combination_count)} selecciones inválidas.`
                      : `${new Set(standardDesign?.cases.map((item) => item.forest_id) ?? []).size} alternativas físicas · ${display(standardDesign?.invalid_combination_count)} selecciones inválidas.`}
                  </p>
                  {fast && resultSource !== undefined ? (
                    <FastResultView
                      result={result}
                      source={resultSource}
                      designId={design.design_id}
                      documentation={documentation ?? undefined}
                      service={service}
                    />
                  ) : standardDesign !== undefined ? (
                    <DesignComparison
                      cases={
                        standardDesign.cases as readonly LayoutCaseResultV2[]
                      }
                      objectiveAliases={objectiveAliases}
                      onSelect={(item, equivalents) => {
                        setCaseDetailError(null);
                        if (resultSource === undefined) {
                          setSelectedCase({ item, equivalents });
                          return;
                        }
                        void resultSource
                          ?.caseDetail(standardDesign.design_id, item.case_id)
                          .then((detail) =>
                            setSelectedCase({
                              item: detail.item as LayoutCaseResultV2,
                              equivalents:
                                detail.equivalents as readonly LayoutCaseResultV2[],
                              dominators:
                                detail.dominators as readonly LayoutCaseResultV2[],
                            }),
                          )
                          .catch((reason: unknown) =>
                            setCaseDetailError(String(reason)),
                          );
                      }}
                    />
                  ) : null}
                  {standardDesign !== undefined &&
                    standardDesign.invalid_combination_summaries.length > 0 && (
                      <details>
                        <summary>Partición de casos inválidos</summary>
                        <ul>
                          {standardDesign.invalid_combination_summaries.map(
                            (item, index) => (
                              <li key={`${item.reason}-${index}`}>
                                {item.reason}: {item.combination_count}{" "}
                                combinaciones ·{" "}
                                {item.conflicting_edges
                                  .map((edge) => edge.join("–"))
                                  .join(", ")}
                                {item.cause
                                  ? ` · ${item.cause}: ${item.explanation}`
                                  : ""}
                              </li>
                            ),
                          )}
                        </ul>
                      </details>
                    )}
                </Panel>
              )}
              {caseDetailError !== null && (
                <p className="srfl-error" role="alert">
                  No se pudo cargar el detalle del caso: {caseDetailError}
                </p>
              )}
            </section>
          ) : (
            <section
              id="result-panel-metrics"
              role="tabpanel"
              aria-labelledby="result-tab-metrics"
              tabIndex={0}
            >
              <MetricsView
                host={host}
                source={resultSource}
                runId={runId}
                designId={design?.design_id ?? ""}
                objectives={result.objective_snapshots}
                designTitles={result.designs}
                components={documentation?.study.components}
                onOpenCase={
                  resultSource === undefined ? undefined : openMetricCase
                }
              />
            </section>
          )}
        </div>
      </div>
      {selectedCase !== null && (
        <CaseDetail
          item={selectedCase.item}
          cases={
            selectedCase.dominators ??
            (standardDesign?.cases as
              | readonly LayoutCaseResultV2[]
              | undefined) ??
            []
          }
          equivalents={selectedCase.equivalents}
          equivalentCount={selectedCase.equivalentCount}
          loading={selectedCase.loading}
          stations={result.stations}
          objectiveAliases={objectiveAliases}
          objectiveDirections={objectiveDirections}
          documentation={documentation ?? undefined}
          service={service}
          onClose={() => setSelectedCase(null)}
        />
      )}
    </main>
  );
}
export function ResultSummary({
  result,
  service,
  onHome,
  template,
  templateBusy,
  onTemplateChange,
  host,
}: {
  result:
    | SingleRowFacilityLayoutResultV2
    | SingleRowFacilityLayoutResult
    | import("@domain-ui-sdk").SingleRowFacilityLayoutResultV21
    | FastResultSummaryV21;
  host?: DomainUiHost;
  service?: AttachmentService;
  onHome: () => void;
  template?: boolean;
  templateBusy?: boolean;
  onTemplateChange?: (enabled: boolean) => void;
}) {
  return result.schema_version === "1.0.0" ? (
    <HistoricalResult result={result} onHome={onHome} />
  ) : (
    <ResultV2
      result={
        result as
          | SingleRowFacilityLayoutResultV2
          | SingleRowFacilityLayoutResultV21
          | FastResultSummaryV21
      }
      host={host}
      service={service}
      onHome={onHome}
      template={template}
      templateBusy={templateBusy}
      onTemplateChange={onTemplateChange}
    />
  );
}
