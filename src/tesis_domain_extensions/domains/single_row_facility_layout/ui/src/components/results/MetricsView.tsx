import { Card } from "@domain-ui-kit";
import type { DomainUiHost } from "@domain-ui-sdk";
import { ActionIconButton, Modal } from "@domain-ui-kit";
import { useEffect, useMemo, useState } from "react";
import { formatCount } from "../../model/display-values";
import type { SrflCase, SrflResultSource } from "../../model/srfl-result-source";
import { formatFractionDecimal } from "./format-fraction";

const metrics = [
  ["base-flexibility", "Flexibilidad conservada frente a la base"],
  ["criterion-extremes", "Extremos por criterio"],
  ["pareto-presence", "Presencia en Pareto"],
  ["component-cooccurrence", "Componentes que aparecen juntos"],
  ["structural-overlap", "Superposición estructural"],
  ["criterion-contributions", "Adyacencias decisivas para un criterio"],
  ["frontier-warnings", "Advertencias en alternativas no dominadas"],
  ["criterion-discrimination", "Capacidad de discriminación de cada criterio"],
  ["base-changes", "Cambios respecto de la base"],
  ["shared-design-patterns", "Patrones compartidos entre diseños"],
  ["nearest-alternative", "Alternativa no dominada más cercana"],
  ["criterion-conflicts", "Conflicto entre criterios"],
  ["pareto-sensitivity", "Sensibilidad de Pareto a un criterio"],
] as const;

type Row = Record<string, unknown>;
type MetricsPage = {
  summary?: Row;
  status?: string;
  total?: number | string;
  rows?: readonly Row[];
  next_cursor?: number | null;
};
type Criterion = { id: string; name: string; unit?: string; direction?: string };
type Context = {
  cases: readonly SrflCase[];
  frontierLoaded: boolean;
  simpleComponentIds: ReadonlySet<string>;
  labels: ReadonlyMap<string, string>;
  criteria: readonly Criterion[];
  designs: ReadonlyMap<string, string>;
};

const asRows = (value: unknown): readonly Row[] => Array.isArray(value) ? value.filter((item): item is Row => typeof item === "object" && item !== null && !Array.isArray(item)) : [];
const asStrings = (value: unknown): string[] => Array.isArray(value) ? value.map(String) : [];
const string = (value: unknown): string => value === null || value === undefined ? "" : String(value);
const number = (value: unknown): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};
const count = (value: unknown): string => {
  try { return formatCount(string(value)); } catch { return "—"; }
};
const singular = (value: unknown, one: string, many: string): string => `${count(value)} ${string(value) === "1" ? one : many}`;
const criterionName = (id: unknown, context: Context): string => context.criteria.find((item) => item.id === id)?.name ?? string(id);
const criterionUnit = (id: unknown, context: Context): string => context.criteria.find((item) => item.id === id)?.unit ?? "";
const caseName = (id: unknown, context: Context): string => context.labels.get(string(id)) ?? "Alternativa del resultado";
const describedCase = (row: Row, context: Context): string => {
  const known = context.labels.get(string(row.case_id));
  if (known) return known;
  if (Array.isArray(row.added_component_ids)) {
    const components = asStrings(row.added_component_ids);
    return components.length ? `Alternativa con ${components.join(", ")}` : "Alternativa base";
  }
  return "Alternativa del resultado";
};
const caseNames = (ids: unknown, context: Context): string => asStrings(ids).map((id) => caseName(id, context)).join(", ");
const edgeNames = (edges: unknown): string => Array.isArray(edges) ? edges.map((edge) => Array.isArray(edge) ? edge.join("–") : string(edge)).join(", ") || "ninguna" : "ninguna";
function BaseCount({ value }: { value: unknown }) {
  const raw = string(value);
  if (!/^\d+$/u.test(raw)) return <>un número aún no disponible de disposiciones</>;
  if (raw.length <= 10) return <>{singular(raw, "disposición", "disposiciones")}</>;
  return <>aproximadamente {raw[0]},{raw.slice(1, 3)} × 10<sup>{raw.length - 1}</sup> disposiciones</>;
}

function decimal(value: unknown, digits = 2): string {
  const raw = string(value);
  if (!raw) return "—";
  const match = /^(-?\d+)\/(\d+)$/u.exec(raw);
  if (match) return formatFractionDecimal({ numerator: match[1]!, denominator: match[2]! }, digits);
  if (/^-?\d+(?:\.\d+)?$/u.test(raw)) {
    const [whole, fraction] = raw.split(".");
    const formatted = count(whole);
    return fraction ? `${formatted},${fraction}` : formatted;
  }
  return raw;
}

function percentage(part: unknown, whole: unknown): string {
  try {
    const numerator = BigInt(string(part));
    const denominator = BigInt(string(whole));
    if (denominator <= 0n) return "—";
    const hundredths = (numerator * 10_000n + denominator / 2n) / denominator;
    if (hundredths === 0n && numerator > 0n) return "menos de 0,01 %";
    return `${hundredths / 100n},${String(hundredths % 100n).padStart(2, "0")} %`;
  } catch { return "—"; }
}
function exactDecimal(value: unknown): { numerator: bigint; denominator: bigint } | null {
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/u.exec(string(value));
  if (match === null) return null;
  const fraction = match[3] ?? "";
  return { numerator: BigInt(`${match[1]}${match[2]}${fraction}`), denominator: 10n ** BigInt(fraction.length) };
}
function compareContributionMagnitude(left: unknown, right: unknown): number {
  const a = exactDecimal(left);
  const b = exactDecimal(right);
  if (a === null || b === null) return a === b ? 0 : a === null ? 1 : -1;
  const absolute = (value: bigint) => value < 0n ? -value : value;
  const difference = absolute(b.numerator) * a.denominator - absolute(a.numerator) * b.denominator;
  return difference < 0n ? -1 : difference > 0n ? 1 : 0;
}
function contributionPercentage(part: unknown, whole: unknown): string {
  const contribution = exactDecimal(part);
  const total = exactDecimal(whole);
  if (contribution === null || total === null) return "—";
  if (total.numerator === 0n) return "No aplica (total cero)";
  const numerator = contribution.numerator * total.denominator * 10_000n;
  const denominator = contribution.denominator * total.numerator;
  const negative = (numerator < 0n) !== (denominator < 0n);
  const rounded = ((numerator < 0n ? -numerator : numerator) + (denominator < 0n ? -denominator : denominator) / 2n)
    / (denominator < 0n ? -denominator : denominator);
  return `${negative && rounded !== 0n ? "−" : ""}${rounded / 100n},${String(rounded % 100n).padStart(2, "0")} %`;
}
function progress(part: unknown, whole: unknown): number {
  try {
    const numerator = BigInt(string(part));
    const denominator = BigInt(string(whole));
    return denominator > 0n ? Math.max(0, Math.min(100, Number(numerator * 1000n / denominator) / 10)) : 0;
  } catch { return 0; }
}
function ShareBar({ part, whole }: { part: unknown; whole: unknown }) {
  return <div className="srfl-metric-share"><span className="srfl-metric-share__track" aria-hidden="true"><span style={{ width: `${progress(part, whole)}%` }} /></span><span>{percentage(part, whole)}</span></div>;
}
function Table({ headings, children }: { headings: readonly string[]; children: React.ReactNode }) {
  return <div className="ui-table-wrap"><table className="ui-table"><thead><tr>{headings.map((heading) => <th key={heading} scope="col">{heading}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;
}
function Empty({ message }: { message: string }) { return <p className="srfl-metric-empty">{message}</p>; }

type PresenceKind = "adjacency" | "component";
function presenceCases(cases: readonly SrflCase[], kind: PresenceKind, id: string): SrflCase[] {
  return cases.filter((item) => kind === "component"
    ? item.added_component_ids.includes(id)
    : item.edges.some((edge) => edge.map(String).sort().join("–") === id));
}
function presenceCriterionValue(item: SrflCase, criterion: Criterion): string {
  if (item.retained_layouts?.objective_id === criterion.id && item.retained_layouts.status === "conclusive" && item.retained_layouts.fraction != null) {
    const value = item.retained_layouts.fraction;
    return percentage(value.numerator, value.denominator);
  }
  const relation = item.rel_closeness?.find((value) => value.objective_id === criterion.id);
  if (relation?.status === "conclusive") return `${formatFractionDecimal(relation.fraction)}${criterion.unit ? ` ${criterion.unit}` : ""}`;
  if (item.captured_flow?.objective_id === criterion.id && item.captured_flow.status === "conclusive" && item.captured_flow.total != null)
    return `${decimal(item.captured_flow.total)} ${item.captured_flow.unit}/${item.captured_flow.horizon}`;
  const adjacency = item.adjacency_values?.find((value) => value.objective_id === criterion.id);
  if (adjacency?.status === "conclusive" && adjacency.total != null)
    return `${decimal(adjacency.total)} ${adjacency.unit}${adjacency.reference_period ? `/${adjacency.reference_period}` : ""}`;
  const exact = "criteria_vector" in item ? item.criteria_vector?.[criterion.id] : undefined;
  if (exact != null) return `${formatFractionDecimal(exact)}${criterion.unit ? ` ${criterion.unit}` : ""}`;
  return "Inconcluso";
}

function FrontierCasesModal({ title, cases, context, onOpenCase, onClose }: { title: string; cases: readonly SrflCase[]; context: Context; onOpenCase?: (caseId: string) => Promise<void>; onClose: () => void }) {
  const [openingCaseId, setOpeningCaseId] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const openCase = (caseId: string) => {
    if (onOpenCase === undefined || openingCaseId !== null) return;
    setOpeningCaseId(caseId);
    setDetailError(null);
    void onOpenCase(caseId).catch((reason: unknown) => setDetailError(String(reason)))
      .finally(() => setOpeningCaseId(null));
  };
  return <Modal title={title} onClose={onClose} className="srfl-presence-modal">
    <p>{singular(cases.length, "caso de la frontera", "casos de la frontera")}</p>
    {cases.length ? <Table headings={["Alternativa", ...context.criteria.map((criterion) => criterion.id === "retained-compatible-layouts" ? "Flexibilidad de distribución" : criterion.name), "Detalle"]}>{cases.map((item) => <tr key={item.case_id}><th scope="row">{caseName(item.case_id, context)}</th>{context.criteria.map((criterion) => <td key={criterion.id}>{presenceCriterionValue(item, criterion)}</td>)}<td><ActionIconButton action="view-details" label={`Ver detalle de ${caseName(item.case_id, context)}`} className="srfl-detail-button" loading={openingCaseId === item.case_id} disabled={onOpenCase === undefined || openingCaseId !== null} onClick={() => openCase(item.case_id)} /></td></tr>)}</Table> : <Empty message="No se encontraron casos en la frontera cargada." />}
    {detailError !== null && <p className="srfl-error" role="alert">No se pudo cargar el detalle del caso: {detailError}</p>}
  </Modal>;
}

function PresenceContent({ page, context, onOpenCase }: { page: MetricsPage; context: Context; onOpenCase?: (caseId: string) => Promise<void> }) {
  const [selectedPresence, setSelectedPresence] = useState<{ kind: PresenceKind; id: string } | null>(null);
  const rows = page.rows ?? [];
  const groups = [["adjacency", "Adyacencias opcionales", "bosques físicos no dominados"], ["component", "Componentes opcionales", "selecciones no dominadas"]] as const;
  const selectedCases = selectedPresence === null ? [] : presenceCases(context.cases, selectedPresence.kind, selectedPresence.id);
  return <>
    <p>Las adyacencias se cuentan por bosque físico distinto; los componentes con varias adyacencias, por selección. Las restricciones fijas de la base no aparecen en el ranking.</p>
    {groups.map(([kind, label, unit]) => {
      const items = rows.filter((row) => row.kind === kind && (kind !== "component" || !context.simpleComponentIds.has(string(row.id))));
      return items.length ? <section key={kind}><h3>{label}</h3><Table headings={[kind === "adjacency" ? "Adyacencia" : "Componente", "Presencia en Pareto", "Casos"]}>{items.map((row) => {
        const id = string(row.id);
        const matching = presenceCases(context.cases, kind, id);
        return <tr key={`${kind}:${id}`}><th scope="row">{id}</th><td><span>{count(row.count)} de {count(row.denominator)} {unit}</span><ShareBar part={row.count} whole={row.denominator} /></td><td>{context.frontierLoaded ? <div className="srfl-presence-open"><span>{singular(matching.length, "caso", "casos")}</span><ActionIconButton action="view-details" label={`Ver casos de ${id}`} className="srfl-detail-button" onClick={() => setSelectedPresence({ kind, id })} /></div> : <span>Cargando casos…</span>}</td></tr>;
      })}</Table></section> : null;
    })}
    {rows.length === 0 && <Empty message="No aparecen restricciones opcionales en la frontera." />}
    {selectedPresence !== null && <FrontierCasesModal title={`Casos con ${selectedPresence.kind === "adjacency" ? "la adyacencia" : "el componente"} ${selectedPresence.id}`} cases={selectedCases} context={context} onOpenCase={onOpenCase} onClose={() => setSelectedPresence(null)} />}
  </>;
}

function CooccurrenceContent({ page, context, onOpenCase }: { page: MetricsPage; context: Context; onOpenCase?: (caseId: string) => Promise<void> }) {
  const [selectedPair, setSelectedPair] = useState<readonly string[] | null>(null);
  const rows = page.rows ?? [];
  const selectedCases = selectedPair === null ? [] : context.cases.filter((item) => selectedPair.every((id) => item.added_component_ids.includes(id)));
  if (rows.length === 0) return <Empty message="Ningún par de componentes opcionales aparece junto en la frontera." />;
  return <>
    <p>Estos componentes opcionales aparecen juntos en algunas selecciones no dominadas. La coincidencia no implica que uno requiera al otro.</p>
    <Table headings={["Componentes", "Juntos", "Por separado", "Casos"]}>{rows.map((row, index) => {
      const pair = asStrings(row.components);
      const matching = context.cases.filter((item) => pair.every((id) => item.added_component_ids.includes(id)));
      return <tr key={index}><th scope="row">{pair.join(" y ")}</th><td>{count(row.together)} de {count(row.denominator)} selecciones<ShareBar part={row.together} whole={row.denominator} /></td><td>{pair[0]}: {count(row.first_alone)} · {pair[1]}: {count(row.second_alone)}</td><td>{context.frontierLoaded ? <div className="srfl-presence-open"><span>{singular(matching.length, "caso", "casos")}</span><ActionIconButton action="view-details" label={`Ver casos con ${pair.join(" y ")}`} className="srfl-detail-button" onClick={() => setSelectedPair(pair)} /></div> : <span>Cargando casos…</span>}</td></tr>;
    })}</Table>
    {selectedPair !== null && <FrontierCasesModal title={`Casos con ${selectedPair.join(" y ")}`} cases={selectedCases} context={context} onOpenCase={onOpenCase} onClose={() => setSelectedPair(null)} />}
  </>;
}

function CriterionContributionsContent({ context, criterionId, onOpenCase }: { context: Context; criterionId: string; onOpenCase?: (caseId: string) => Promise<void> }) {
  const [openingCaseId, setOpeningCaseId] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [casePage, setCasePage] = useState(0);
  useEffect(() => { setCasePage(0); }, [criterionId]);
  const cases = useMemo(() => context.cases.flatMap((item) => {
    const objective = item.adjacency_values?.find((value) => value.objective_id === criterionId)
      ?? (item.captured_flow?.objective_id === criterionId ? item.captured_flow : undefined);
    if (objective?.status !== "conclusive" || objective.total == null || !objective.contributions?.length) return [];
    const contributions = [...objective.contributions].sort((left, right) =>
      compareContributionMagnitude(left.total, right.total)
      || `${left.first_station_id}–${left.second_station_id}`.localeCompare(`${right.first_station_id}–${right.second_station_id}`));
    return [{ item, objective, contributions }];
  }), [context.cases, criterionId]);
  const visible = cases.slice(casePage * 50, (casePage + 1) * 50);
  const openCase = (caseId: string) => {
    if (onOpenCase === undefined || openingCaseId !== null) return;
    setOpeningCaseId(caseId);
    setDetailError(null);
    void onOpenCase(caseId).catch((reason: unknown) => setDetailError(String(reason)))
      .finally(() => setOpeningCaseId(null));
  };
  if (!context.frontierLoaded) return <Empty message="Cargando alternativas de la frontera…" />;
  if (cases.length === 0) return <Empty message="Este criterio no tiene aportes por adyacencia en la frontera." />;
  return <>
    <p>Se muestran hasta tres adyacencias por alternativa, ordenadas por la magnitud de su aporte. El porcentaje conserva el signo respecto del total del caso; si el total es cero, no se calcula.</p>
    <Table headings={["Alternativa", "Aportes principales", "Total del caso", "Detalle"]}>{visible.map(({ item, objective, contributions }) => {
      const caseId = item.case_id;
      const unit = `${objective.unit}${"horizon" in objective ? ` por ${objective.horizon}` : objective.reference_period ? ` por ${objective.reference_period}` : ""}`;
      return <tr key={caseId}><th scope="row">{caseName(caseId, context).split(" · ")[0]}</th><td><ol className="srfl-contribution-list">{contributions.slice(0, 3).map((entry) => <li key={`${entry.first_station_id}:${entry.second_station_id}`}><span>{entry.first_station_id}–{entry.second_station_id}</span><span className={string(entry.total).startsWith("-") ? "srfl-metric-negative" : ""}>{decimal(entry.total)} {unit}</span><span>{contributionPercentage(entry.total, objective.total)}</span></li>)}</ol>{contributions.length > 3 && <small className="srfl-contribution-more">+{contributions.length - 3} adyacencias más en el detalle</small>}</td><td>{decimal(objective.total)} {unit}</td><td><ActionIconButton action="view-details" label={`Ver detalle de ${caseName(caseId, context)}`} className="srfl-detail-button" loading={openingCaseId === caseId} disabled={onOpenCase === undefined || openingCaseId !== null} onClick={() => openCase(caseId)} /></td></tr>;
    })}</Table>
    {cases.length > 50 && <div className="srfl-contribution-pagination"><button type="button" disabled={casePage === 0} onClick={() => setCasePage((current) => current - 1)}>Anteriores</button><span>Página {casePage + 1} de {Math.ceil(cases.length / 50)}</span><button type="button" disabled={(casePage + 1) * 50 >= cases.length} onClick={() => setCasePage((current) => current + 1)}>Siguientes</button></div>}
    {detailError !== null && <p className="srfl-error" role="alert">No se pudo cargar el detalle del caso: {detailError}</p>}
  </>;
}

function FlexibilityContent({ page, context, onOpenCase }: { page: MetricsPage; context: Context; onOpenCase?: (caseId: string) => Promise<void> }) {
  const summary = page.summary ?? {};
  const rows = page.rows ?? [];
  const total = Number(page.total ?? 0);
  const [openingCaseId, setOpeningCaseId] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const openCase = (caseId: string) => {
    if (onOpenCase === undefined || openingCaseId !== null) return;
    setOpeningCaseId(caseId);
    setDetailError(null);
    void onOpenCase(caseId).catch((reason: unknown) => setDetailError(String(reason)))
      .finally(() => setOpeningCaseId(null));
  };
  const distribution = asRows(summary.distribution);
  const focus = asObject(summary.focus_distribution);
  const focusCounts = Array.isArray(focus.counts) ? focus.counts : [];
  const focusUpper = number(focus.upper_percent);
  const complete = page.status === "conclusive";
  if (!complete) {
    return <Empty message={`Todavía no se puede comparar toda la frontera: hay ${count(summary.missing_cases ?? 0)} casos sin un conteo compatible confirmado o la clasificación de Pareto es inconclusa.`} />;
  }
  if (total === 0) return <Empty message="No hay casos no dominados para comparar con la base." />;
  return <>
    <p>Cada barra cuenta casos de la frontera de Pareto según el porcentaje de disposiciones que conservan. El 100 % equivale a la base: <BaseCount value={summary.base_layout_count} />.</p>
    {string(summary.base_layout_count).length > 10 && <details className="srfl-metric-exact"><summary>Ver cantidad exacta de la base</summary><span>{formatCount(string(summary.base_layout_count))} disposiciones</span></details>}
    {distribution.length === 4 && <div className="srfl-flexibility-chart" role="group" aria-label="Distribución de flexibilidad de toda la frontera">
      <h3>Distribución completa · 0 % a 100 %</h3>
      <ol className="srfl-flexibility-histogram">{distribution.map((bucket, index) => {
        const amount = number(bucket.count);
        const label = index === 3 ? "75 % a 100 %" : `${string(bucket.from_percent)} % a menos de ${string(bucket.to_percent)} %`;
        return <li key={index}>
          <span>{label}</span>
          <span className="srfl-flexibility-histogram__track" aria-hidden="true"><span style={{ width: `${progress(bucket.count, summary.denominator)}%` }} /></span>
          <strong>{singular(amount, "caso", "casos")}</strong>
        </li>;
      })}</ol>
      {focusUpper > 0 && focusCounts.length === 5 && <div className="srfl-flexibility-focus" role="group" aria-label={`Detalle de la concentración entre cero y ${focusUpper} por ciento`}>
        <h3>Detalle de la concentración · 0 % a {focusUpper} %</h3>
        <p>Fuera del tramo: {singular(focus.above_cases, "caso", "casos")}.</p>
        <ol className="srfl-flexibility-histogram">{focusCounts.map((amount, index) => {
          const from = (focusUpper * index / 5).toLocaleString("es-AR", { maximumFractionDigits: 1 });
          const to = (focusUpper * (index + 1) / 5).toLocaleString("es-AR", { maximumFractionDigits: 1 });
          return <li key={index}>
            <span>{index === 4 ? `${from} % a ${to} %` : `${from} % a menos de ${to} %`}</span>
            <span className="srfl-flexibility-histogram__track" aria-hidden="true"><span style={{ width: `${progress(amount, focus.within_cases)}%` }} /></span>
            <strong>{singular(amount, "caso", "casos")}</strong>
          </li>;
        })}</ol>
      </div>}
    </div>}
    <details className="srfl-flexibility-details">
      <summary>Ver casos y porcentajes exactos</summary>
      <Table headings={["Caso", "Disposiciones conservadas frente a la base", "Detalle"]}>{rows.map((row, index) => {
        const caseId = string(row.case_id);
        const label = caseName(caseId, context).replace(/^Alternativa\b/u, "Caso");
        return <tr key={caseId || index}><td>{label}</td><td><ShareBar part={row.numerator} whole={row.denominator} /></td><td><ActionIconButton action="view-details" label={`Ver detalle de ${label}`} className="srfl-detail-button" loading={openingCaseId === caseId} disabled={onOpenCase === undefined || openingCaseId !== null} onClick={() => openCase(caseId)} /></td></tr>;
      })}</Table>
    </details>
    {detailError !== null && <p className="srfl-error" role="alert">No se pudo cargar el detalle del caso: {detailError}</p>}
  </>;
}

function MetricContent({ id, page, context, criterionId, onOpenCase }: { id: string; page: MetricsPage; context: Context; criterionId: string; onOpenCase?: (caseId: string) => Promise<void> }) {
  const rows = page.rows ?? [];
  const summary = page.summary ?? {};
  if (page.status === "not_applicable") return <Empty message={string(summary.message) || "Esta métrica no aplica a este diseño."} />;
  if (id === "base-flexibility") return <FlexibilityContent page={page} context={context} onOpenCase={onOpenCase} />;
  if (page.status === "inconclusive") return <Empty message="Este análisis no es concluyente con los resultados disponibles." />;
  if (id === "criterion-extremes") return rows.length ? <>
    <p>Los extremos se calculan sólo entre alternativas no dominadas. La dirección de cada criterio determina cuál valor es mejor.</p>
    <Table headings={["Criterio", "Mejor valor", "Alternativas con ese valor", "Otro extremo"]}>{rows.map((row, index) => <tr key={index}><th scope="row">{string(row.name)}{row.unit ? ` · ${row.unit}` : ""}</th><td>{decimal(row.best)} {criterionUnit(row.criterion_id, context)}</td><td>{singular(row.best_case_count, "alternativa", "alternativas")}{asStrings(row.best_case_ids).length <= 3 && asStrings(row.best_case_ids).length > 0 ? `: ${caseNames(row.best_case_ids, context)}` : ""}</td><td>{decimal(row.worst)} {criterionUnit(row.criterion_id, context)}</td></tr>)}</Table>
  </> : <Empty message="No hay extremos calculables." />;
  if (id === "pareto-presence") return <PresenceContent page={page} context={context} onOpenCase={onOpenCase} />;
  if (id === "component-cooccurrence") return <CooccurrenceContent page={page} context={context} onOpenCase={onOpenCase} />;
  if (id === "structural-overlap") return rows.length ? <><p>Distintas selecciones pueden imponer exactamente las mismas adyacencias.</p><ul className="srfl-metric-groups">{rows.map((row, index) => <li key={index}><strong>{singular(row.count, "selección", "selecciones")} con el mismo bosque</strong><span>Componentes presentes en el grupo: {asStrings(row.components).join(", ") || "ninguno"}.</span><span>{caseNames(row.case_ids, context)}</span></li>)}</ul></> : <Empty message="Cada selección no dominada produce un bosque diferente." />;
  if (id === "criterion-contributions") return <CriterionContributionsContent context={context} criterionId={criterionId} onOpenCase={onOpenCase} />;
  if (id === "frontier-warnings") return rows.length ? <><p>{singular(summary.warnings, "advertencia", "advertencias")} en alternativas no dominadas. Son avisos; no invalidan la alternativa.</p><Table headings={["Alternativa", "Adyacencia", "Motivo", "Explicación"]}>{rows.map((row, index) => <tr key={index}><td>{caseName(row.case_id, context)}</td><th scope="row">{string(row.adjacency)}</th><td>{warningName(row.cause)}</td><td>{string(row.explanation)}</td></tr>)}</Table></> : <Empty message="No hay advertencias en las alternativas no dominadas." />;
  if (id === "criterion-discrimination") return rows.length ? <><p>Un criterio distingue mejor estas alternativas cuando sus valores son diferentes. Esto describe sólo la frontera.</p><Table headings={["Criterio", "Valor observado", "Alternativas que lo comparten"]}>{rows.map((row, index) => <tr key={index}><th scope="row">{string(row.name)}</th><td>{decimal(row.value)} {string(row.unit)}</td><td>{count(row.count)} de {count(summary.frontier_cases)}<ShareBar part={row.count} whole={summary.frontier_cases} /></td></tr>)}</Table></> : <Empty message="No hay valores concluyentes para comparar." />;
  if (id === "base-changes") return rows.length ? <><p>Se cuentan las adyacencias nuevas de cada alternativa respecto de las fijadas en la base.</p><Table headings={["Alternativa", "Cambio respecto de la base", "Adyacencias agregadas"]}>{rows.map((row, index) => <tr key={index}><td>{caseName(row.case_id, context)}</td><td>{singular(row.new_adjacencies, "adyacencia nueva", "adyacencias nuevas")}</td><td>{edgeNames(row.edges)}</td></tr>)}</Table></> : <Empty message="No hay cambios adicionales respecto de la base." />;
  if (id === "shared-design-patterns") return rows.length ? <><p>Una adyacencia obligatoria se distingue de otra elegida en una alternativa no dominada.</p><Table headings={["Adyacencia", "Situación por diseño"]}>{rows.map((row, index) => <tr key={index}><th scope="row">{string(row.adjacency)}</th><td><ul className="srfl-metric-design-list">{asRows(row.designs).map((item, position) => <li key={position}><strong>{context.designs.get(string(item.design_id)) ?? string(item.design_id)}</strong>: {designState(item.state)}{item.frontier_status === "inconclusive" ? " · frontera inconclusa" : ""}</li>)}</ul></td></tr>)}</Table></> : <Empty message="No hay adyacencias para comparar entre diseños." />;
  if (id === "nearest-alternative") return rows.length ? <><p>Entre los bosques distintos de la frontera, estas alternativas requieren la menor cantidad de cambios de adyacencias.</p>{rows.map((row, index) => <section className="srfl-metric-comparison" key={index}><h3>{caseName(row.case_id, context)} · {singular(row.distance, "cambio", "cambios")}</h3><div className="srfl-metric-comparison__edges"><p><strong>Quitar:</strong> {edgeNames(row.removed)}</p><p><strong>Agregar:</strong> {edgeNames(row.added)}</p></div><Table headings={["Criterio", "Alternativa elegida", "Alternativa cercana", "Cambio"]}>{Object.entries(asObject(row.criteria)).map(([criterionId, value]) => { const comparison = asObject(value); return <tr key={criterionId}><th scope="row">{criterionName(criterionId, context)}</th><td>{decimal(comparison.selected)} {criterionUnit(criterionId, context)}</td><td>{decimal(comparison.alternative)} {criterionUnit(criterionId, context)}</td><td>{decimal(comparison.change)} {criterionUnit(criterionId, context)}</td></tr>; })}</Table></section>)}</> : <Empty message="No hay otra alternativa no dominada con un bosque diferente." />;
  if (id === "criterion-conflicts") {
    const pairs = asRows(summary.by_criterion_pair);
    return pairs.length ? <><p>Se comparan pares de alternativas no dominadas. Una mejora en un criterio puede acompañarse de una pérdida en otro; los empates quedan fuera del porcentaje.</p><Table headings={["Criterios", "Conflictos", "Mejoras conjuntas"]}>{pairs.map((pair, index) => <tr key={index}><th scope="row">{asStrings(pair.criteria).map((item) => criterionName(item, context)).join(" y ")}</th><td>{count(pair.conflict ?? 0)} de {count(pair.denominator)} comparaciones<ShareBar part={pair.conflict ?? 0} whole={pair.denominator} /></td><td>{count(pair["joint-improvement"] ?? 0)} comparaciones · {count(pair.ties_excluded ?? 0)} empates excluidos</td></tr>)}</Table>{summary.expected_two_criterion_frontier_tradeoff === true && <p>Con exactamente dos criterios activos, este conflicto es esperable por la definición de Pareto. Compará alternativas concretas para entender el intercambio.</p>}{rows.length > 0 && <details><summary>Ver ejemplos de comparaciones</summary><ul className="srfl-metric-groups">{rows.slice(0, 10).map((row, index) => <li key={index}><strong>{row.outcome === "conflict" ? "Intercambio entre criterios" : "Mejora conjunta"}</strong><span>{asStrings(row.cases).map((item) => caseName(item, context)).join(" frente a ")}</span><span>{asStrings(row.criteria).map((criterionId) => `${criterionName(criterionId, context)}: ${asStrings(asObject(row.values)[criterionId]).map((value) => decimal(value)).join(" frente a ")}`).join(" · ")}</span></li>)}</ul></details>}</> : <Empty message="No hay pares de criterios comparables sin empates." />;
  }
  if (id === "pareto-sensitivity") return <><p>Se excluye temporalmente un criterio y se vuelve a calcular la frontera con todos los casos válidos confirmados. El resultado oficial no cambia.</p><div className="srfl-metric-comparison__edges"><p><strong>Frontera oficial:</strong> {singular(summary.official_frontier, "alternativa", "alternativas")}</p><p><strong>Sin {criterionName(summary.excluded_criterion_id, context)}:</strong> {singular(summary.alternative_frontier, "alternativa", "alternativas")}</p></div>{rows.length > 0 && <Table headings={["Alternativa", "Resultado de la simulación"]}>{rows.map((row, index) => <tr key={index}><th scope="row">{describedCase(row, context)}</th><td>{row.status === "enters" ? "Entra en la nueva frontera" : row.status === "leaves" ? "Sale de la nueva frontera" : "Permanece en ambas fronteras"}</td></tr>)}</Table>}</>;
  return null;
}
function asObject(value: unknown): Row { return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Row : {}; }
function warningName(value: unknown): string {
  const names: Record<string, string> = { safety: "Seguridad", cross_contamination: "Contaminación cruzada", noise: "Ruido", temperature: "Temperatura", privacy: "Privacidad", interference: "Interferencia", process: "Proceso" };
  return names[string(value)] ?? string(value);
}
function designState(value: unknown): string {
  const names: Record<string, string> = { obligatoria: "obligatoria en la base", "presente en frontera": "presente en una alternativa no dominada", "opcional y ausente": "opcional, ausente de la frontera" };
  return names[string(value)] ?? string(value);
}

function MetricCard({ id, title, host, runId, designId, context, onOpenCase }: {
  id: string; title: string; host?: DomainUiHost; runId: string; designId: string; context: Context; onOpenCase?: (caseId: string) => Promise<void>;
}) {
  const [page, setPage] = useState<MetricsPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cursor, setCursor] = useState(0);
  const [criterionId, setCriterionId] = useState("");
  const [caseId, setCaseId] = useState("");
  const requiresCriterion = id === "pareto-sensitivity" || id === "criterion-contributions";
  const requiresCase = id === "nearest-alternative";
  const availableCriteria = id === "criterion-contributions"
    ? context.criteria.filter((item) => item.id === "captured-adjacency-flow" || item.id.startsWith("adjacency-"))
    : context.criteria;
  useEffect(() => { setCursor(0); setPage(null); setCriterionId(""); setCaseId(""); }, [id, designId, runId]);
  useEffect(() => {
    let active = true;
    if (host?.getResultMetrics === undefined || (requiresCriterion && criterionId === "") || (requiresCase && caseId === "")) {
      setPage(null);
      return () => { active = false; };
    }
    setBusy(true);
    setError(null);
    setPage(null);
    void host.getResultMetrics<MetricsPage>({
      domain_run_id: runId, metric_id: id,
      ...(id !== "shared-design-patterns" ? { design_id: designId } : {}),
      ...(criterionId ? { criterion_id: criterionId } : {}),
      ...(caseId ? { case_id: caseId } : {}), cursor,
    }).then((value) => { if (active) setPage(value); })
      .catch((reason: unknown) => { if (active) setError(String(reason)); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [host, runId, id, designId, cursor, criterionId, caseId, requiresCriterion, requiresCase]);
  return <Card className="srfl-metric-card" id={`metric-${id}`} aria-labelledby={`metric-title-${id}`}>
    <h2 id={`metric-title-${id}`}>{title}</h2>
    {id === "criterion-contributions" && <p>Elegí una matriz para ver qué adyacencias forman su valor en las alternativas no dominadas.</p>}
    {id === "nearest-alternative" && <p>Elegí una alternativa de la frontera. Se buscará otra que requiera la menor cantidad de cambios de adyacencias.</p>}
    {id === "pareto-sensitivity" && <p>Explorá cómo cambiaría la frontera si se dejara de considerar un criterio. Esta simulación usa los resultados confirmados y puede tardar.</p>}
    {requiresCriterion && availableCriteria.length > 0 && <label>{id === "pareto-sensitivity" ? "Criterio que se excluirá de la simulación" : "Criterio cuyos aportes querés ver"}<select value={criterionId} onChange={(event) => { setCriterionId(event.target.value); setCursor(0); }}><option value="">Elegí un criterio</option>{availableCriteria.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
    {requiresCriterion && availableCriteria.length === 0 && <Empty message="Este experimento no tiene criterios con aportes por adyacencia." />}
    {requiresCase && <label>Alternativa que querés comparar<select value={caseId} onChange={(event) => { setCaseId(event.target.value); setCursor(0); }}><option value="">Elegí una alternativa</option>{context.cases.map((item) => <option key={item.case_id} value={item.case_id}>{caseName(item.case_id, context)}</option>)}</select></label>}
    {requiresCase && context.cases.length === 0 && <Empty message="Cargando las alternativas de la frontera…" />}
    {host?.getResultMetrics === undefined && <Empty message="Las métricas no están disponibles en esta versión de la aplicación." />}
    {requiresCriterion && criterionId === "" && availableCriteria.length > 0 && <Empty message="Elegí un criterio para ver este análisis." />}
    {requiresCase && caseId === "" && context.cases.length > 0 && <Empty message="Elegí una alternativa para encontrar la más cercana." />}
    {busy && <p role="status">Calculando esta métrica…</p>}
    {error !== null && <p className="srfl-error" role="alert">No se pudo cargar esta métrica: {error}</p>}
    {page !== null && <><MetricContent id={id} page={page} context={context} criterionId={criterionId} onOpenCase={onOpenCase} />{id !== "criterion-contributions" && page.next_cursor != null && <button type="button" className="srfl-metric-next" onClick={() => setCursor(page.next_cursor!)}>Ver más resultados</button>}</>}
  </Card>;
}

export function MetricsView({ host, source, runId, designId, objectives, designTitles, components, onOpenCase }: {
  host?: DomainUiHost;
  source?: SrflResultSource;
  runId: string;
  designId: string;
  objectives: readonly { definition: Criterion }[];
  designTitles: readonly { design_id: string; design_title: string }[];
  components?: readonly { id: string; station_ids: readonly string[] }[];
  onOpenCase?: (caseId: string) => Promise<void>;
}) {
  const [cases, setCases] = useState<readonly SrflCase[]>([]);
  const [frontierLoaded, setFrontierLoaded] = useState(false);
  useEffect(() => {
    let active = true;
    setCases([]);
    setFrontierLoaded(false);
    if (source === undefined) { setFrontierLoaded(true); return () => { active = false; }; }
    void source.frontier(designId).then((items) => { if (active) setCases(items); }).catch(() => { if (active) setCases([]); })
      .finally(() => { if (active) setFrontierLoaded(true); });
    return () => { active = false; };
  }, [source, designId]);
  const context = useMemo<Context>(() => {
    const ordered = [...cases].sort((a, b) => a.case_id.localeCompare(b.case_id));
    return {
      cases: ordered,
      frontierLoaded,
      simpleComponentIds: new Set(components?.filter((item) => item.station_ids.length === 2).map((item) => item.id) ?? []),
      labels: new Map(ordered.map((item, index) => [item.case_id, `Alternativa ${index + 1}${item.added_component_ids.length ? ` · ${item.added_component_ids.join(", ")}` : " · base"}`])),
      criteria: objectives.map((item) => item.definition),
      designs: new Map(designTitles.map((item) => [item.design_id, item.design_title])),
    };
  }, [cases, frontierLoaded, objectives, designTitles, components]);
  return <div className="srfl-metrics-view" aria-label="Métricas del diseño">{metrics.map(([id, title]) => <MetricCard key={id} id={id} title={title} host={host} runId={runId} designId={designId} context={context} onOpenCase={id === "base-flexibility" || id === "pareto-presence" || id === "component-cooccurrence" || id === "criterion-contributions" ? onOpenCase : undefined} />)}</div>;
}
export const metricIndex = metrics;
