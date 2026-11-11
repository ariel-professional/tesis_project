import { ActionButton, ButtonVariant } from "@domain-ui-kit";
import type { AttachmentService, LayoutCaseResultV2, LayoutCaseResultV21, SingleRowFacilityLayoutDraftV2, StationV2 } from "@domain-ui-sdk";
import { useCallback, useEffect, useState } from "react";
import { type FastResultSummaryV21, type SrflCaseDetail, type SrflResultSource } from "../../model/srfl-result-source";
import { CaseDetail } from "./CaseDetail";
import { CaseDetailButton, IndexedParetoChart } from "./DesignComparison";
import { formatFractionDecimal } from "./format-fraction";

const criterionOrder = (id: string) => `criterion:${id}`;

function criterionValue(item: LayoutCaseResultV21, objectiveId: string): string {
  const adjacency = item.adjacency_values?.find((value) => value.objective_id === objectiveId);
  if (adjacency?.total != null) {
    const period = adjacency.reference_period ? `/${adjacency.reference_period}` : "";
    return `${String(adjacency.total).replace(".", ",")} ${adjacency.unit}${period}`;
  }
  if (item.captured_flow?.objective_id === objectiveId && item.captured_flow.total != null) {
    const period = item.captured_flow.horizon ? `/${item.captured_flow.horizon}` : "";
    return `${String(item.captured_flow.total).replace(".", ",")} ${item.captured_flow.unit}${period}`;
  }
  const exact = item.criteria_vector?.[objectiveId];
  if (exact === undefined) return "Inconcluso";
  if (objectiveId === "retained-compatible-layouts" && item.retained_layouts?.fraction != null)
    return formatFractionDecimal(item.retained_layouts.fraction);
  if (objectiveId.startsWith("rel-closeness-")) return `${exact.numerator}/${exact.denominator}`;
  return formatFractionDecimal(exact);
}

export function normalizeFastCaseDetail(fetched: SrflCaseDetail): SrflCaseDetail {
  const item = fetched.item as LayoutCaseResultV21;
  const differences = fetched.dominators.flatMap((candidate) => {
    const vector = (candidate as LayoutCaseResultV21).criteria_vector ?? {};
    const target = item.criteria_vector ?? {};
    return Object.keys(vector).flatMap((objectiveId) => {
      const preferred = vector[objectiveId];
      const other = target[objectiveId];
      if (preferred === undefined || other === undefined || (preferred.numerator === other.numerator && preferred.denominator === other.denominator)) return [];
      return [{ objective_id: objectiveId, preferred_case_id: candidate.case_id, other_case_id: item.case_id, preferred_value: preferred, other_value: other }];
    });
  });
  return {
    ...fetched,
    item: {
      ...item,
      pareto_classification: {
        ...item.pareto_classification,
        status: "conclusive" as const,
        dominated: fetched.dominators.length > 0,
        pareto_optimal: fetched.dominators.length === 0,
        dominated_by_case_ids: fetched.dominators.map((candidate) => candidate.case_id),
        differences,
      },
    } as LayoutCaseResultV21,
  };
}

export function FastResultView({ result, source, designId, documentation, service }: {
  result: FastResultSummaryV21;
  source: SrflResultSource;
  designId: string;
  documentation?: SingleRowFacilityLayoutDraftV2;
  service?: AttachmentService;
}) {
  const [order, setOrder] = useState("case");
  const [direction, setDirection] = useState<"ascending" | "descending">("ascending");
  const [page, setPage] = useState(0);
  const [cache, setCache] = useState<Map<string, Awaited<ReturnType<typeof source.casePage>>>>(new Map());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<SrflCaseDetail | null>(null);
  const [loadingDetailCaseId, setLoadingDetailCaseId] = useState<string | null>(null);
  const [frontier, setFrontier] = useState<readonly LayoutCaseResultV21[]>([]);
  const [frontierLoaded, setFrontierLoaded] = useState(false);
  const design = result.designs.find((item) => item.design_id === designId);
  const showExactChart = design !== undefined && BigInt(design.valid_case_count) <= 10000n;
  const canReduceVisualNoise = design !== undefined && BigInt(design.valid_case_count) < 10000n;
  const objectives = result.objective_snapshots;
  const aliases = Object.fromEntries(objectives.map(({ definition }) => [definition.id, `${definition.name} · ${definition.direction === "maximize" ? "↑ Maximizar" : "↓ Minimizar"}`]));
  const directions = Object.fromEntries(objectives.map(({ definition }) => [definition.id, definition.direction]));
  const cacheKey = `${designId}\0${order}\0${direction}\0${page}`;
  const current = cache.get(cacheKey);

  useEffect(() => {
    setPage(0);
    setDetail(null);
    setError(null);
  }, [designId]);

  useEffect(() => {
    if (current !== undefined) return;
    let active = true;
    setLoading(true);
    setError(null);
    void source.casePage(designId, order, direction, page).then((value) => {
      if (!active) return;
      setCache((previous) => {
        const next = new Map(previous);
        next.set(cacheKey, value);
        while (next.size > 20) next.delete(next.keys().next().value!);
        return next;
      });
    }).catch((reason: unknown) => {
      if (active) setError(String(reason));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [cacheKey, current, designId, direction, order, page, source]);

  useEffect(() => {
    let active = true;
    setFrontier([]);
    setFrontierLoaded(false);
    void source.frontier(designId).then((items) => {
      if (active) { setFrontier(items as LayoutCaseResultV21[]); setFrontierLoaded(true); }
    }).catch((reason: unknown) => { if (active) setError(String(reason)); });
    return () => { active = false; };
  }, [designId, source]);
  const loadPoints = useCallback((x: string, y: string) => source.plotPoints(designId, x, y), [designId, source]);
  const loadProjection = useCallback((x: string, y: string, xScale: "automatic" | "linear" | "square-root" | "adjusted-log" | "percentile", yScale: "automatic" | "linear" | "square-root" | "adjusted-log" | "percentile", xLogK: number, yLogK: number, level: 0 | 1 | 2, section: "groups" | "frontier_positions") => source.plotProjection({ design_id: designId, x_objective_id: x, y_objective_id: y, x_scale: xScale, y_scale: yScale, x_log_k: xLogK, y_log_k: yLogK, level, section }), [designId, source]);

  const detailCase = async (caseId: string) => {
    if (loadingDetailCaseId !== null) return;
    setLoadingDetailCaseId(caseId);
    try {
      const presentDetail = (fetched: SrflCaseDetail) => setDetail(normalizeFastCaseDetail(fetched));
      await source.caseDetail(designId, caseId, presentDetail);
    } catch (reason) { setError(String(reason)); }
    finally { setLoadingDetailCaseId(null); }
  };
  const changeOrder = (nextOrder: string) => {
    if (order === nextOrder) setDirection((currentDirection) => currentDirection === "ascending" ? "descending" : "ascending");
    else { setOrder(nextOrder); setDirection("ascending"); }
    setPage(0);
  };
  const sortHeader = (key: string, label: string, sortable = true) => <th key={key} aria-sort={order === key ? direction : "none"}>
    {sortable
      ? <button type="button" className="srfl-sort-button" onClick={() => changeOrder(key)}>{label}<span aria-hidden="true">{order === key ? direction === "ascending" ? " ↑" : " ↓" : ""}</span></button>
      : label}
  </th>;

  if (design === undefined) return null;
  return <>
    <section id="resultado-pareto" className="srfl-pareto-summary" aria-label="Resumen de casos no dominados">
      <header><h3>Casos no dominados</h3><p>{frontierLoaded ? `${frontier.length} de ${design.valid_case_count} casos válidos pertenecen a la frontera.` : "Cargando la frontera…"}</p></header>
      {frontierLoaded && frontier.length === 0 && <p>No hay una frontera concluyente para este diseño.</p>}
      {frontier.length > 0 && <div className="ui-table-wrap"><table className="ui-table"><thead><tr><th>Caso</th>{objectives.map(({ definition }) => <th key={definition.id}>{aliases[definition.id]}</th>)}<th>Acción</th></tr></thead>
        <tbody>{frontier.map((item) => <tr key={item.case_id}><td><strong>{item.case_id.slice(0, 12)}</strong><small>{item.component_ids.join(", ") || "Sin componentes"}</small></td>
          {objectives.map(({ definition }) => <td key={definition.id}>{criterionValue(item, definition.id)}</td>)}
          <td><CaseDetailButton item={item as LayoutCaseResultV2} equivalents={[item as LayoutCaseResultV2]} loading={loadingDetailCaseId === item.case_id} disabled={loadingDetailCaseId !== null && loadingDetailCaseId !== item.case_id} onSelect={(selected) => void detailCase(selected.case_id)} /></td></tr>)}</tbody>
      </table></div>}
    </section>
    <section id="resultado-grafico" className="srfl-result-chart" aria-label="Gráfico de la frontera de Pareto">
      {objectives.length > 0 && <IndexedParetoChart key={designId} objectives={objectives.map(({ definition }) => ({ id: definition.id, label: aliases[definition.id] ?? definition.name }))} frontierCases={frontier as unknown as readonly LayoutCaseResultV2[]} loadPoints={loadPoints} loadProjection={showExactChart ? undefined : loadProjection} visualNoiseReductionAvailable={canReduceVisualNoise} onSelectCaseId={(caseId) => void detailCase(caseId)} />}
    </section>
    {error !== null && <p className="srfl-error" role="alert">No se pudo cargar la consulta: {error}</p>}
    {loading && <p role="status">Cargando casos…</p>}
    {current !== undefined && <section id="resultado-tabla" className="srfl-all-cases" aria-label="Todos los casos válidos">
      <header><h3>Todos los casos válidos</h3><p>Orden global y paginación del resultado confirmado.</p></header>
      <div className="ui-table-wrap"><table className="ui-table"><thead><tr>{sortHeader("case", "Caso")}{sortHeader("components", "Componentes")}{objectives.map(({ definition }) => sortHeader(criterionOrder(definition.id), aliases[definition.id] ?? definition.name))}{sortHeader("classification", "Clasificación", false)}<th><span className="sr-only">Acción</span></th></tr></thead>
        <tbody>{current.items.map((item) => <tr key={item.case_id}><td><code>{item.case_id.slice(0, 12)}</code></td><td>{item.component_ids.join(", ") || "—"}</td>
          {objectives.map(({ definition }) => {
            return <td key={definition.id}>{criterionValue(item as LayoutCaseResultV21, definition.id)}</td>;
          })}
          <td>{(item as LayoutCaseResultV21).scientific_status === "inconclusive" ? "Inconcluso" : item.pareto_classification.pareto_optimal ? "No dominado" : "Dominado"}</td>
          <td><CaseDetailButton item={item as LayoutCaseResultV2} equivalents={[item as LayoutCaseResultV2]} loading={loadingDetailCaseId === item.case_id} disabled={loadingDetailCaseId !== null && loadingDetailCaseId !== item.case_id} onSelect={(selected) => void detailCase(selected.case_id)} /></td></tr>)}</tbody>
      </table></div>
      <footer className="srfl-result-toolbar"><span>{current.total} casos · página {page + 1}</span>
        <ActionButton action="previous" label="Anterior" variant={ButtonVariant.Secondary} loading={loading && page > 0} disabled={page === 0 || loading} onClick={() => setPage((value) => value - 1)} />
        <ActionButton action="next" label="Siguiente" variant={ButtonVariant.Secondary} loading={loading && (page + 1) * 50 < current.total} disabled={(page + 1) * 50 >= current.total || loading} onClick={() => setPage((value) => value + 1)} />
      </footer>
    </section>}
    {detail !== null && <CaseDetail item={detail.item as LayoutCaseResultV2} cases={detail.dominators as readonly LayoutCaseResultV2[]} equivalents={detail.equivalents as readonly LayoutCaseResultV2[]} equivalentCount={detail.equivalent_count} loading={detail.loading} stations={result.stations as StationV2[]} objectiveAliases={aliases} objectiveDirections={directions} documentation={documentation} service={service} onClose={() => setDetail(null)} />}
  </>;
}
