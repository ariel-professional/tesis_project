import { Button, ButtonVariant, EntityTable } from "@domain-ui-kit";
import { Fragment } from "react";
import type { SrflEditorDraft } from "../../model/editor-draft.types";
import { effectiveEvidence } from "../../model/evidence";
import { SrflEvidenceField } from "../evidence/SrflEvidence";

export function AdjacencyTable({ draft, onChange, onDelete, expanded, onExpandedChange }: { draft: SrflEditorDraft; onChange: (clientKey: string, values: { id?: string }) => void; onDelete: (clientKey: string) => void; expanded: readonly string[]; onExpandedChange: (keys: readonly string[]) => void }) {
  return <EntityTable headers={["Restricción", "ID", "Acciones"]} empty={draft.study.components.length === 0}>{draft.study.components.map((component) => {
    const evidence = effectiveEvidence(draft, component.clientKey);
    const opened = expanded.includes(component.clientKey);
    return <Fragment key={component.clientKey}>
      <tr>
        <td>{component.stationIds.join(" → ")}</td>
        <td><input className="ui-input" aria-label={`ID de ${component.id}`} value={component.id} onChange={(event) => onChange(component.clientKey, { id: event.target.value })} /></td>
        <td><div className="srfl-restriction-actions">
          <Button variant={ButtonVariant.Secondary} aria-expanded={opened} aria-controls={`detail-${component.clientKey}`} onClick={() => onExpandedChange(opened ? expanded.filter((key) => key !== component.clientKey) : [...expanded, component.clientKey])}>
            Detalle
            {(evidence.description || evidence.attachments.length > 0) && <span className="srfl-evidence-indicator" title="Tiene antecedentes" role="img" aria-label="Tiene antecedentes"><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M4 1.5h5l3 3v10H4zM9 1.5v3h3M6 8h4M6 11h4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg></span>}
          </Button>
          <Button variant={ButtonVariant.Danger} onClick={() => onDelete(component.clientKey)}>Eliminar</Button>
        </div></td>
      </tr>
      <tr id={`detail-${component.clientKey}`} hidden={!opened}><td colSpan={3}>{opened && <SrflEvidenceField owner={component.clientKey} label={`Detalle de ${component.stationIds.join(" → ")}`} />}</td></tr>
    </Fragment>;
  })}</EntityTable>;
}
