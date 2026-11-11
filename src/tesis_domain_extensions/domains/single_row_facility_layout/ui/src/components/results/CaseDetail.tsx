import {
  ActionIconButton,
  Button,
  ButtonVariant,
  EvidenceEditor,
  Modal,
  SelectField,
} from "@domain-ui-kit";
import { useEffect, useMemo, useState } from "react";
import type {
  AttachmentService,
  LayoutCaseResultV2,
  SingleRowFacilityLayoutDraftV2,
  StationV2,
} from "@domain-ui-sdk";
import { DocumentationPanel } from "../evidence/DocumentationPanel";
import { ForestDiagram } from "./ForestDiagram";
import {
  formatFractionDetailParts,
  type ExactFractionValue,
} from "./format-fraction";
import { canonicalPairKey } from "../../model/matrix-pairs";
import {
  formatCount,
  formatEngineeringCount,
} from "../../model/display-values";
function list(values: readonly string[]): string {
  return values.length > 0 ? values.join(", ") : "Ninguno";
}
type ObjectiveDirection = "maximize" | "minimize";
type ExactValue = ExactFractionValue;

function rational(
  value: ExactValue | string,
): { numerator: bigint; denominator: bigint } | null {
  if (typeof value !== "string") {
    try {
      return {
        numerator: BigInt(value.numerator),
        denominator: BigInt(value.denominator),
      };
    } catch {
      return null;
    }
  }
  const match = /^(-?\d+)(?:\.(\d+))?$/.exec(value);
  if (match === null) return null;
  const decimals = match[2] ?? "";
  return {
    numerator: BigInt(`${match[1]}${decimals}`),
    denominator: 10n ** BigInt(decimals.length),
  };
}
function improvement(
  preferred: ExactValue | string,
  other: ExactValue | string,
  direction: ObjectiveDirection,
): string {
  const left = rational(preferred);
  const right = rational(other);
  if (
    left === null ||
    right === null ||
    left.denominator === 0n ||
    right.denominator === 0n
  )
    return direction === "maximize" ? "Valor mayor" : "Valor menor";
  let numerator =
    left.numerator * right.denominator - right.numerator * left.denominator;
  if (numerator < 0n) numerator = -numerator;
  const relativeDenominator =
    left.denominator *
    (right.numerator < 0n ? -right.numerator : right.numerator);
  if (relativeDenominator === 0n)
    return direction === "maximize" ? "Aumenta desde 0" : "Disminuye desde 0";
  const positiveDenominator =
    relativeDenominator < 0n ? -relativeDenominator : relativeDenominator;
  const hundredths =
    (numerator * 10_000n + positiveDenominator / 2n) / positiveDenominator;
  const action = direction === "maximize" ? "Aumenta" : "Disminuye";
  if (hundredths === 0n && numerator !== 0n)
    return `${action} en menos de 0,01 %`;
  const decimals = String(hundredths % 100n)
    .padStart(2, "0")
    .replace(/0+$/u, "");
  const percentage = `${hundredths / 100n}${decimals === "" ? "" : `,${decimals}`} %`;
  return `${action} en un ${percentage}`;
}
function ExactNumber({
  value,
}: {
  value: ExactValue | string | null | undefined;
}) {
  if (typeof value === "string") return <>{value}</>;
  const detail = formatFractionDetailParts(value);
  return (
    <>
      {detail.beforeRepeat}
      {detail.repeating !== null && (
        <span className="srfl-repeating-decimal">{detail.repeating}</span>
      )}
      {detail.afterRepeat}
    </>
  );
}
function Improvement({
  preferred,
  other,
  direction,
}: {
  preferred: ExactValue | string;
  other: ExactValue | string;
  direction: ObjectiveDirection;
}) {
  return <>{improvement(preferred, other, direction)}</>;
}
function objectiveName(alias: string): string {
  return alias.replace(/ · [↑↓] (?:Maximizar|Minimizar)$/u, "");
}

type SelectedEdge = readonly [string, string];
const CAUSE_LABELS: Record<string, string> = {
  safety: "Seguridad",
  cross_contamination: "Contaminación cruzada",
  noise: "Ruido",
  temperature: "Temperatura",
  privacy: "Privacidad",
  interference: "Interferencia",
  process: "Proceso",
};
function includesEdge(
  path: readonly string[],
  [first, second]: SelectedEdge,
): boolean {
  const target = canonicalPairKey(first, second);
  return path
    .slice(0, -1)
    .some(
      (station, index) =>
        canonicalPairKey(station, path[index + 1]!) === target,
    );
}
function EdgeMetadata({
  edge,
  item,
  stations,
  documentation,
  service,
}: {
  edge: SelectedEdge;
  item: LayoutCaseResultV2;
  stations: readonly StationV2[];
  documentation: SingleRowFacilityLayoutDraftV2;
  service?: AttachmentService;
}) {
  const names = new Map(stations.map((station) => [station.id, station.name]));
  const key = canonicalPairKey(edge[0], edge[1]);
  const relation =
    documentation.decision_model.rel_closeness?.requirements.find(
      (candidate) =>
        canonicalPairKey(
          candidate.first_station_id,
          candidate.second_station_id,
        ) === key,
    );
  const policy =
    documentation.decision_model.undesired_prescribed_adjacencies?.find(
      (candidate) =>
        canonicalPairKey(
          candidate.first_station_id,
          candidate.second_station_id,
        ) === key,
    );
  const components = documentation.study.components.filter(
    (component) =>
      item.component_ids.includes(component.id) &&
      includesEdge(component.station_ids, edge),
  );
  const matrices = documentation.decision_model.adjacency_flow;
  const quantitative =
    matrices == null
      ? []
      : Array.isArray(matrices)
        ? matrices.map((matrix) => ({
            id: matrix.id,
            name: matrix.name,
            description: matrix.description,
            unit: matrix.unit,
            period: matrix.reference_period,
            provenance: matrix.provenance,
            entries: matrix.entries
              .filter(
                (entry) =>
                  canonicalPairKey(
                    entry.from_station_id,
                    entry.to_station_id,
                  ) === key,
              )
              .map((entry) => ({
                from: entry.from_station_id,
                to: entry.to_station_id,
                value: entry.value,
              })),
          }))
        : [
            {
              id: "historical-flow",
              name: "Flujo entre áreas",
              description: "",
              unit: matrices.unit,
              period: matrices.horizon,
              provenance: matrices.provenance,
              entries: matrices.entries
                .filter(
                  (entry) =>
                    canonicalPairKey(
                      entry.from_station_id,
                      entry.to_station_id,
                    ) === key,
                )
                .map((entry) => ({
                  from: entry.from_station_id,
                  to: entry.to_station_id,
                  value: entry.quantity,
                })),
            },
          ];
  return (
    <section className="srfl-edge-detail" aria-live="polite">
      <header>
        <div>
          <span>Arista seleccionada</span>
          <h4>
            {names.get(edge[0]) ?? edge[0]} – {names.get(edge[1]) ?? edge[1]}
          </h4>
        </div>
        <code>
          {edge[0]} · {edge[1]}
        </code>
      </header>
      <div className="srfl-edge-detail__grid">
        <article>
          <h5>Prioridad REL</h5>
          {relation === undefined ? (
            <p>No aplica.</p>
          ) : (
            <dl className="srfl-case-details">
              <dt>Nivel</dt>
              <dd>{relation.level}</dd>
              <dt>Motivo operativo</dt>
              <dd>{relation.reason}</dd>
              <dt>Fuente</dt>
              <dd>{relation.provenance}</dd>
            </dl>
          )}
          {policy !== undefined && (
            <div className="srfl-edge-policy">
              <strong>
                {policy.policy === "forbidden"
                  ? "Relación prohibida"
                  : "Relación advertida"}
              </strong>
              <p>
                {CAUSE_LABELS[policy.cause] ?? policy.cause}:{" "}
                {policy.explanation}
              </p>
              <small>Fuente: {policy.provenance}</small>
            </div>
          )}
        </article>
        <article>
          <h5>Valores cuantitativos</h5>
          {quantitative.length === 0 ? (
            <p>Sin matrices cuantitativas.</p>
          ) : (
            quantitative.map((matrix) => (
              <div className="srfl-edge-matrix" key={matrix.id}>
                <strong>{matrix.name}</strong>
                {matrix.description && <p>{matrix.description}</p>}
                <ul>
                  {matrix.entries.map((entry) => (
                    <li key={`${entry.from}-${entry.to}`}>
                      {names.get(entry.from) ?? entry.from} →{" "}
                      {names.get(entry.to) ?? entry.to}:{" "}
                      <strong>
                        {entry.value} {matrix.unit}
                        {matrix.period ? `/${matrix.period}` : ""}
                      </strong>
                    </li>
                  ))}
                </ul>
                <small>Fuente: {matrix.provenance}</small>
              </div>
            ))
          )}
        </article>
      </div>
      <div className="srfl-edge-components">
        <h5>Restricciones que incorporan esta arista</h5>
        {components.length === 0 ? (
          <p>No se identificó una restricción documental asociada.</p>
        ) : (
          components.map((component) => (
            <article key={component.id}>
              <header>
                <strong>{component.station_ids.join(" → ")}</strong>
                <span>
                  {item.mandatory_component_ids.includes(component.id)
                    ? "Obligatoria del diseño"
                    : "Agregada en este caso"}
                </span>
              </header>
              <EvidenceEditor
                readOnly
                service={service}
                value={{
                  description: component.description ?? "",
                  attachments: component.attachments ?? [],
                }}
              />
            </article>
          ))
        )}
      </div>
    </section>
  );
}

export function CaseDetail({
  item,
  cases = [],
  stations,
  onClose,
  documentation,
  service,
  objectiveAliases = {},
  objectiveDirections = {},
  equivalents,
  equivalentCount,
  loading = false,
}: {
  item: LayoutCaseResultV2;
  cases?: readonly LayoutCaseResultV2[];
  stations: readonly StationV2[];
  onClose: () => void;
  documentation?: SingleRowFacilityLayoutDraftV2;
  service?: AttachmentService;
  objectiveAliases?: Readonly<Record<string, string>>;
  objectiveDirections?: Readonly<Record<string, ObjectiveDirection>>;
  equivalents?: readonly LayoutCaseResultV2[];
  equivalentCount?: number;
  loading?: boolean;
}) {
  const equivalentCases = equivalents ?? [item];
  const dominanceGroups = useMemo(() => {
    const differences = item.pareto_classification.differences ?? [];
    const ids = item.pareto_classification.dominated_by_case_ids ?? [];
    return ids
      .map((caseId) => ({
        caseId,
        differences: differences.filter(
          (difference) => difference.preferred_case_id === caseId,
        ),
      }))
      .sort(
        (left, right) =>
          right.differences.length - left.differences.length ||
          left.caseId.localeCompare(right.caseId, "es"),
      );
  }, [item]);
  const [selectedDominator, setSelectedDominator] = useState(
    dominanceGroups[0]?.caseId ?? "",
  );
  const [copiedReference, setCopiedReference] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<SelectedEdge | null>(null);
  useEffect(() => {
    setSelectedDominator(dominanceGroups[0]?.caseId ?? "");
    setCopiedReference(null);
    setSelectedEdge(null);
  }, [item.case_id]);
  const selectedDominance =
    dominanceGroups.find((group) => group.caseId === selectedDominator) ??
    dominanceGroups[0];
  const preferredCase = cases.find(
    (candidate) => candidate.case_id === selectedDominance?.caseId,
  );
  const copyReference = (caseId: string) => {
    if (navigator.clipboard === undefined) return;
    void navigator.clipboard
      .writeText(caseId)
      .then(() => setCopiedReference(caseId))
      .catch(() => undefined);
  };
  const pareto =
    item.pareto_classification.status !== "conclusive"
      ? "Inconcluso"
      : item.pareto_classification.pareto_optimal
        ? "No dominado"
        : "Dominado";
  return (
    <Modal
      title="Detalle del caso"
      className="srfl-case-modal"
      onClose={onClose}
    >
      {documentation && (
        <DocumentationPanel
          config={documentation}
          service={service}
          componentIds={item.component_ids}
          designId={item.design_id}
        />
      )}
      <section className="srfl-case-section">
        <h3>Restricciones y adyacencias</h3>
        <ForestDiagram
          item={item}
          stations={stations}
          selectedEdge={selectedEdge}
          onSelectEdge={
            documentation === undefined
              ? undefined
              : (edge) =>
                  setSelectedEdge((current) =>
                    current !== null &&
                    canonicalPairKey(current[0], current[1]) ===
                      canonicalPairKey(edge[0], edge[1])
                      ? null
                      : edge,
                  )
          }
        />
        {documentation !== undefined && selectedEdge !== null && (
          <EdgeMetadata
            edge={selectedEdge}
            item={item}
            stations={stations}
            documentation={documentation}
            service={service}
          />
        )}
        <p className="srfl-note">
          {documentation === undefined
            ? "El gráfico representa restricciones de adyacencia, no una disposición física final."
            : "Seleccioná una arista para consultar sus antecedentes y datos de relación."}
        </p>
      </section>
      <section className="srfl-case-section">
        <h3>Identificación y estado</h3>
        <dl className="srfl-case-details">
          <dt>Referencia del caso</dt>
          <dd>
            <code>{item.case_id}</code>
          </dd>
          <dt>
            {item.core_run_id == null ? "Referencia del caso" : "Run CORE"}
          </dt>
          <dd>
            <code>{item.core_run_id ?? item.case_id}</code>
          </dd>
          <dt>Clasificación</dt>
          <dd>{pareto}</dd>
          <dt>Componentes</dt>
          <dd>{list(item.component_ids)}</dd>
          <dt>Componentes agregados</dt>
          <dd>{list(item.added_component_ids)}</dd>
          <dt>Aristas prescriptas</dt>
          <dd>{item.prescribed_edge_count}</dd>
          <dt>Selecciones equivalentes</dt>
          <dd>
            {equivalentCount ?? equivalentCases.length}
            {loading ? " (cargando…)" : ""}
          </dd>
        </dl>
        {equivalentCases.length > 1 && (
          <div className="srfl-equivalent-selections">
            <p>
              Estas selecciones producen exactamente las mismas adyacencias y se
              comparan como una única alternativa física:
            </p>
            <ul className="srfl-wrapping-list">
              {equivalentCases.map((equivalent) => (
                <li key={equivalent.case_id}>
                  {list(equivalent.component_ids)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
      {loading && (
        <p role="status">Cargando equivalencias y clasificación del caso…</p>
      )}
      {item.retained_layouts != null && (
        <section className="srfl-case-section">
          <h3>Disponibilidad</h3>
          <dl className="srfl-case-details">
            <dt>Fracción exacta</dt>
            <dd className="srfl-exact-number">
              <ExactNumber value={item.retained_layouts.fraction} />
            </dd>
            <dt>Compatibles</dt>
            <dd>
              {formatEngineeringCount(
                item.retained_layouts.compatible_layout_count,
              )}
            </dd>
            <dt>Base</dt>
            <dd>
              {formatEngineeringCount(item.retained_layouts.base_layout_count)}
            </dd>
          </dl>
        </section>
      )}
      {(item.rel_closeness?.length ?? 0) > 0 && (
        <section className="srfl-case-section">
          <h3>Cobertura de prioridades de cercanía</h3>
          <div className="srfl-case-cards">
            {item.rel_closeness?.map((result) => (
              <article key={result.objective_id}>
                <h4>
                  {objectiveAliases[result.objective_id] ??
                    `Prioridad REL · nivel ${result.level}`}
                </h4>
                <dl className="srfl-case-details">
                  <dt>Resultado</dt>
                  <dd className="srfl-exact-number">
                    <ExactNumber value={result.fraction} />
                  </dd>
                  <dt>Incluidas como adyacencia obligatoria</dt>
                  <dd>
                    {result.guaranteed_pairs
                      .map((pair) => pair.join("–"))
                      .join(", ") || "Ninguno"}
                  </dd>
                  <dt>No incluidas</dt>
                  <dd>
                    {result.pending_pairs
                      .map((pair) => pair.join("–"))
                      .join(", ") || "Ninguno"}
                  </dd>
                </dl>
              </article>
            ))}
          </div>
        </section>
      )}
      {item.captured_flow != null && (
        <section className="srfl-case-section">
          <h3>Flujo entre áreas adyacentes</h3>
          <p className="srfl-case-highlight">
            {item.captured_flow.total ?? "Inconcluso"} {item.captured_flow.unit}
            /{item.captured_flow.horizon}
          </p>
          <ul className="srfl-wrapping-list">
            {item.captured_flow.contributions?.map((entry) => (
              <li key={`${entry.first_station_id}-${entry.second_station_id}`}>
                {entry.first_station_id}–{entry.second_station_id}:{" "}
                {entry.forward_quantity}
                {entry.reverse_quantity != null
                  ? ` + ${entry.reverse_quantity}`
                  : ""}{" "}
                = {entry.total}
              </li>
            ))}
          </ul>
        </section>
      )}
      {(
        (
          item as LayoutCaseResultV2 & {
            adjacency_values?: Array<{
              objective_id: string;
              matrix_id: string;
              status: string;
              total?: string | number | null;
              unit: string;
              reference_period?: string | null;
              direction: "maximize" | "minimize";
              contributions?: Array<{
                first_station_id: string;
                second_station_id: string;
                forward_value: string | number;
                reverse_value?: string | number | null;
                total: string | number;
              }>;
            }>;
          }
        ).adjacency_values ?? []
      ).map((result) => (
        <section className="srfl-case-section" key={result.objective_id}>
          <h3>{objectiveAliases[result.objective_id] ?? result.matrix_id}</h3>
          <p className="srfl-case-highlight">
            {result.total ?? "Inconcluso"} {result.unit}
            {result.reference_period ? `/${result.reference_period}` : ""}
          </p>
          <p>
            {result.direction === "maximize"
              ? "↑ Se prefiere un valor mayor"
              : "↓ Se prefiere un valor menor"}
          </p>
          <ul className="srfl-wrapping-list">
            {result.contributions?.map((entry) => (
              <li key={`${entry.first_station_id}-${entry.second_station_id}`}>
                {entry.first_station_id}–{entry.second_station_id}:{" "}
                {entry.forward_value}
                {entry.reverse_value != null
                  ? ` + ${entry.reverse_value}`
                  : ""}{" "}
                = {entry.total}
              </li>
            ))}
          </ul>
        </section>
      ))}
      {(item.findings?.length ?? 0) > 0 && (
        <section className="srfl-case-section">
          <h3>Advertencias no vinculantes</h3>
          <ul className="srfl-wrapping-list">
            {item.findings?.map((finding) => (
              <li
                key={`${finding.first_station_id}-${finding.second_station_id}`}
              >
                {finding.first_station_id}–{finding.second_station_id}:{" "}
                {finding.cause} · {finding.explanation} ({finding.provenance})
              </li>
            ))}
          </ul>
        </section>
      )}
      {(item.pareto_classification.dominated_by_case_ids?.length ?? 0) > 0 && (
        <section
          className="srfl-case-section srfl-dominance"
          aria-labelledby="dominance-title"
        >
          <header className="srfl-dominance__header">
            <div>
              <h3 id="dominance-title">Dominancia</h3>
              <p>
                Estas alternativas son iguales o mejores en todos los criterios
                y estrictamente mejores en al menos uno.
              </p>
            </div>
            <div className="srfl-dominance__summary">
              <span>Dominado</span>
              <strong>
                {dominanceGroups.length} alternativa
                {dominanceGroups.length === 1 ? "" : "s"}
              </strong>
            </div>
          </header>
          <div className="srfl-dominance__layout">
            <div className="srfl-dominance__select">
              <SelectField
                label="Comparar con"
                value={selectedDominance?.caseId ?? ""}
                options={dominanceGroups.map((group) => ({
                  value: group.caseId,
                  label: `${group.caseId.slice(0, 12)}… · ${group.differences.length} mejora${group.differences.length === 1 ? "" : "s"}`,
                }))}
                onChange={(event) => setSelectedDominator(event.target.value)}
              />
            </div>
            <nav
              className="srfl-dominance__cases"
              aria-label="Alternativas dominantes"
            >
              <h4>Alternativas dominantes</h4>
              {dominanceGroups.map((group) => (
                <Button
                  key={group.caseId}
                  variant={
                    group.caseId === selectedDominance?.caseId
                      ? ButtonVariant.Primary
                      : ButtonVariant.Secondary
                  }
                  className="srfl-dominance__case"
                  aria-pressed={group.caseId === selectedDominance?.caseId}
                  onClick={() => setSelectedDominator(group.caseId)}
                >
                  <span>
                    <code>{group.caseId.slice(0, 12)}…</code>
                    <small>
                      {group.differences.length} mejora
                      {group.differences.length === 1 ? "" : "s"}
                    </small>
                  </span>
                  <span aria-hidden="true">›</span>
                </Button>
              ))}
            </nav>
            {selectedDominance !== undefined && (
              <article
                className="srfl-dominance__comparison"
                aria-live="polite"
              >
                <header>
                  <div>
                    <span>Comparación con</span>
                    <code title={selectedDominance.caseId}>
                      {selectedDominance.caseId.slice(0, 12)}…
                    </code>
                  </div>
                  <ActionIconButton
                    action="copy"
                    label="Copiar referencia completa"
                    onClick={() => copyReference(selectedDominance.caseId)}
                  />
                </header>
                <div className="ui-table-wrap">
                  <table className="ui-table srfl-dominance__table">
                    <thead>
                      <tr>
                        <th>Criterio</th>
                        <th>Objetivo</th>
                        <th>Este caso</th>
                        <th>Alternativa</th>
                        <th>Mejora</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedDominance.differences.map((difference) => {
                        const alias =
                          objectiveAliases[difference.objective_id] ??
                          difference.objective_id;
                        const direction =
                          objectiveDirections[difference.objective_id] ??
                          (alias.includes("↓") ? "minimize" : "maximize");
                        return (
                          <tr key={difference.objective_id}>
                            <th scope="row">{objectiveName(alias)}</th>
                            <td>
                              <span
                                className={`srfl-direction srfl-direction--${direction}`}
                              >
                                {direction === "maximize"
                                  ? "↑ Maximizar"
                                  : "↓ Minimizar"}
                              </span>
                            </td>
                            <td>
                              {difference.objective_id ===
                              "retained-compatible-layouts" ? (
                                formatCount(
                                  item.retained_layouts
                                    ?.compatible_layout_count,
                                )
                              ) : (
                                <ExactNumber value={difference.other_value} />
                              )}
                            </td>
                            <td>
                              {difference.objective_id ===
                              "retained-compatible-layouts" ? (
                                formatCount(
                                  preferredCase?.retained_layouts
                                    ?.compatible_layout_count,
                                )
                              ) : (
                                <ExactNumber
                                  value={difference.preferred_value}
                                />
                              )}
                            </td>
                            <td>
                              <strong>
                                <Improvement
                                  preferred={difference.preferred_value}
                                  other={difference.other_value}
                                  direction={direction}
                                />
                              </strong>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </article>
            )}
          </div>
          {copiedReference !== null && (
            <p className="srfl-dominance__copied" role="status">
              Referencia completa copiada.
            </p>
          )}
        </section>
      )}
      {item.diagnostics.length > 0 && (
        <section className="srfl-case-section">
          <h3>Diagnósticos</h3>
          <ul className="srfl-wrapping-list">
            {item.diagnostics.map((entry) => (
              <li key={`${entry.core_code}-${entry.message}`}>
                {entry.message} <code>{entry.core_code}</code>
              </li>
            ))}
          </ul>
        </section>
      )}
      {item.limitations.length > 0 && (
        <section className="srfl-case-section">
          <h3>Limitaciones</h3>
          <ul className="srfl-wrapping-list">
            {item.limitations.map((entry) => (
              <li key={`${entry.code}-${entry.message}`}>{entry.message}</li>
            ))}
          </ul>
        </section>
      )}
    </Modal>
  );
}
