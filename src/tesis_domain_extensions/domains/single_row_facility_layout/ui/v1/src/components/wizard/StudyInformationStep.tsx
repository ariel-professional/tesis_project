import { SrflEvidenceField } from "../evidence/SrflEvidence";
import { SwitchField, TextField } from "@domain-ui-kit";
import type { SrflEditorDraft } from "../../model/editor-draft.types";

export function StudyInformationStep({
  draft,
  onChange,
}: {
  draft: SrflEditorDraft;
  onChange: (draft: SrflEditorDraft) => void;
}) {
  return (
    <section className="srfl-step">
      <div className="srfl-step__intro">
        <h2>Información del estudio</h2>
      </div>
      <div className="srfl-form-grid">
        <TextField
          label="Título"
          description="Nombre del experimento"
          value={draft.study.title}
          onChange={(event) => onChange({ ...draft, study: { ...draft.study, title: event.target.value } })}
        />
        <SrflEvidenceField owner="study" fallback={{ draft, onChange }} />
        {draft.templateEvidence && <>
          <SwitchField label="Importar adjuntos" description="Incluye archivos y enlaces de la plantilla en estudio, restricciones y diseños." checked={draft.templateEvidence.importAttachments} onChange={(importAttachments) => onChange({ ...draft, templateEvidence: { ...draft.templateEvidence!, importAttachments } })} />
          <SwitchField label="Importar descripción/detalle de las restricciones" description="Las descripciones del estudio y de los diseños se conservan siempre." checked={draft.templateEvidence.importRestrictionDescriptions} onChange={(importRestrictionDescriptions) => onChange({ ...draft, templateEvidence: { ...draft.templateEvidence!, importRestrictionDescriptions } })} />
        </>}
      </div>
      <div className="ui-panel">
        <span className="ui-eyebrow">Origen</span>
        <strong>{draft.origin.label}</strong>
      </div>
    </section>
  );
}
