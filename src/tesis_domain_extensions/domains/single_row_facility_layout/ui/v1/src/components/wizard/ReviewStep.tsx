import { DocumentationSections } from "../evidence/DocumentationSections";
import { SrflEvidenceField } from "../evidence/SrflEvidence";
import { ActionButton, Button, Card, MetricCard, SwitchField } from "@domain-ui-kit";
import type { SrflEditorDraft } from "../../model/editor-draft.types";

export function ReviewStep({ draft, estimate, validated, busy, error, template, onTemplateChange, onExecute }: { draft: SrflEditorDraft; estimate: number | string | null; validated: boolean; busy: boolean; error: string | null; template: boolean; onTemplateChange: (value: boolean) => void; onExecute: () => void }) {
  return <section className="srfl-step"><div className="srfl-step__intro"><h2>Revisión</h2><p>Revisá el resumen antes de preparar la ejecución.</p></div><div className="srfl-metrics"><MetricCard label="Estaciones" value={draft.study.stations.length} /><MetricCard label="Restricciones" value={draft.study.components.length} /><MetricCard label="Diseños" value={draft.study.designs.length} /><MetricCard label="Combinaciones teóricas" value={busy ? "Calculando…" : estimate ?? "—"} /></div><Card><div className="srfl-review-title"><div><h3>{draft.study.title}</h3>{draft.study.description !== "" && <p>{draft.study.description}</p>}<small>{draft.origin.label}</small></div></div><details className="srfl-evidence-details"><summary>Antecedentes del estudio, restricciones y diseños</summary><DocumentationSections
  study={{ key: "study", title: draft.study.title, content: <SrflEvidenceField owner="study" readOnly /> }}
  designs={draft.study.designs.map((item) => ({ key: item.clientKey, title: item.title, content: <SrflEvidenceField owner={item.clientKey} readOnly /> }))}
  restrictions={draft.study.components.map((item) => ({ key: item.clientKey, title: `${item.stationIds.join(" → ")} · ${item.id}`, content: <SrflEvidenceField owner={item.clientKey} readOnly /> }))}
/></details><SwitchField label="Guardar como plantilla" description="La definición quedará disponible para crear otros experimentos." checked={template} disabled={busy} onChange={onTemplateChange} />{error !== null && <p className="srfl-error" role="alert">{error}</p>}<div className="srfl-actions"><ActionButton action="calculate" label={busy ? "Comprobando…" : "Preparar y ejecutar"} loading={busy} onClick={onExecute} disabled={!validated || busy} /></div></Card></section>;
}
