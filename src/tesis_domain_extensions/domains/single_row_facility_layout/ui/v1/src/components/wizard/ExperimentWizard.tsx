import { SrflEvidenceProvider, useEvidenceActivity } from "../evidence/SrflEvidence";
import { ActionButton, Button, ButtonVariant, PageHeader, Wizard, type FieldError } from "@domain-ui-kit";
import type { DomainUiHost, SingleRowFacilityLayoutDraft } from "@domain-ui-sdk";
import { useEffect, useRef, useState } from "react";
import type { SrflEditorDraft } from "../../model/editor-draft.types";
import { SrflEditorStep } from "../../model/editor-state.types";
import { toScientificDraft } from "../../model/mappers";
import { validateAll, validateStep } from "../../model/validation";
import { AdjacenciesStep } from "./AdjacenciesStep";
import { AdvancedConfigurationStep } from "./AdvancedConfigurationStep";
import { DesignsStep } from "./DesignsStep";
import { ReviewStep } from "./ReviewStep";
import { StationsStep } from "./StationsStep";
import { StudyInformationStep } from "./StudyInformationStep";

const STEPS = [
  { id: SrflEditorStep.Information, label: "Información" }, { id: SrflEditorStep.Stations, label: "Estaciones" },
  { id: SrflEditorStep.Adjacencies, label: "Restricciones" }, { id: SrflEditorStep.Designs, label: "Diseños" },
  { id: SrflEditorStep.AdvancedConfiguration, label: "Avanzado" }, { id: SrflEditorStep.Review, label: "Revisión" },
] as const;

function WizardContent({ host, draft, revision, onChange, onExit, onExecute }: { host: DomainUiHost; draft: SrflEditorDraft; revision: number; onChange: (draft: SrflEditorDraft) => void; onExit: () => void; onExecute: (draft: SingleRowFacilityLayoutDraft, saveAsTemplate: boolean) => void }) {
  const pending = useEvidenceActivity();
  const latestRevision = useRef(revision); latestRevision.current = revision;
  const validationRequest = useRef(0);
  const [step, setStep] = useState(SrflEditorStep.Information); const [errors, setErrors] = useState<FieldError[]>([]);
  const [highestEnabledIndex, setHighestEnabledIndex] = useState(0);
  const [saveAsTemplate, setSaveAsTemplate] = useState(false);
  const [estimate, setEstimate] = useState<number | string | null>(null); const [validatedRevision, setValidatedRevision] = useState<number | null>(null); const [busy, setBusy] = useState(false); const [remoteError, setRemoteError] = useState<string | null>(null);
  const validated = validatedRevision === revision && pending === 0;
  const validateReview = async () => {
    const request = ++validationRequest.current;
    const local = validateAll(draft); setErrors(local); setRemoteError(null); if (local.length > 0) { setValidatedRevision(null); return; }
    setBusy(true); try { const scientific = toScientificDraft(draft); await host.validateStudy(scientific); if (host.attachments) { for (const entity of [scientific.study, ...scientific.study.components, ...scientific.study.designs]) { for (const file of entity.attachments ?? []) { if (file.kind === "file") await host.attachments.readRange(file, 0, 0); } } } await host.validateForest(scientific); const result = await host.estimateCombinations(scientific); if (request === validationRequest.current && latestRevision.current === revision) { setEstimate(result.theoretical_combinations); setValidatedRevision(revision); } } catch (reason) { if (request === validationRequest.current && latestRevision.current === revision) { setValidatedRevision(null); setRemoteError(String(reason)); } } finally { if (request === validationRequest.current) setBusy(false); }
  };
  useEffect(() => { if (step === SrflEditorStep.Review && pending === 0 && validatedRevision !== revision) void validateReview(); }, [step, revision, pending]);
  const selectStep = (next: SrflEditorStep) => { if (pending > 0) return; const nextIndex = STEPS.findIndex((item) => item.id === next); if (nextIndex > highestEnabledIndex) return; setErrors([]); setStep(next); };
  const index = STEPS.findIndex((item) => item.id === step); const next = STEPS[index + 1]?.id; const previous = STEPS[index - 1]?.id;
  const goNext = async () => {
    if (next === undefined) return;
    const found = validateStep(draft, step); setErrors(found); setRemoteError(null); if (found.length > 0) return;
    if (step === SrflEditorStep.Designs) {
      setBusy(true);
      try { await host.validateForest(toScientificDraft(draft)); }
      catch (reason) { setRemoteError(String(reason)); return; }
      finally { setBusy(false); }
    }
    const nextIndex = index + 1; setHighestEnabledIndex((value) => Math.max(value, nextIndex)); setErrors([]); setStep(next);
  };
  return <main className="srfl-page"><PageHeader eyebrow="Nuevo estudio · SRFL 1.0.0" title={draft.study.title || "Experimento sin título"} description="Completá cada etapa, podés volver atrás antes de preparar la ejecución." actions={<Button variant={ButtonVariant.Ghost} onClick={onExit}>Salir del borrador</Button>} /><Wizard items={STEPS} current={step} highestEnabledIndex={highestEnabledIndex} onSelect={selectStep} />
    <div className="srfl-wizard-actions">{previous !== undefined && <ActionButton action="previous" label="Anterior" variant={ButtonVariant.Secondary} onClick={() => selectStep(previous)} />}<span />{next !== undefined && <ActionButton action="next" label={busy ? "Comprobando…" : "Siguiente"} loading={busy} onClick={() => void goNext()} disabled={busy || pending > 0} />}</div>
    {errors.length > 0 && <div className="srfl-validation" role="alert"><strong>Revisá esta etapa</strong><ul>{errors.map((error) => <li key={`${error.field}-${error.message}`}>{error.message}</li>)}</ul></div>}
    {remoteError !== null && step !== SrflEditorStep.Review && <p className="srfl-error" role="alert">{remoteError}</p>}
    {step === SrflEditorStep.Information && <StudyInformationStep draft={draft} onChange={onChange} />}
    {step === SrflEditorStep.Stations && <StationsStep draft={draft} onChange={onChange} />}
    {step === SrflEditorStep.Adjacencies && <AdjacenciesStep draft={draft} onChange={onChange} />}
    {step === SrflEditorStep.Designs && <DesignsStep draft={draft} onChange={onChange} />}
    {step === SrflEditorStep.AdvancedConfiguration && <AdvancedConfigurationStep draft={draft} onChange={onChange} />}
    {step === SrflEditorStep.Review && <ReviewStep draft={draft} estimate={estimate} validated={validated} busy={busy || pending > 0} error={remoteError} template={saveAsTemplate} onTemplateChange={setSaveAsTemplate} onExecute={() => onExecute(toScientificDraft(draft), saveAsTemplate)} />}
  </main>;
}

export function ExperimentWizard(props: Parameters<typeof WizardContent>[0]) {
  return <SrflEvidenceProvider key={props.draft.study.id} draft={props.draft} onChange={props.onChange} service={props.host.attachments}><WizardContent {...props} /></SrflEvidenceProvider>;
}
