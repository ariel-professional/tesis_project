import {
  ActionButton,
  Button,
  ButtonVariant,
  PageHeader,
  Wizard,
  type FieldError,
} from "@domain-ui-kit";
import type {
  DomainUiHost,
  SingleRowFacilityLayoutDraftV2,
  SingleRowFacilityLayoutDraftV21,
} from "@domain-ui-sdk";
import { useEffect, useRef, useState } from "react";
import type { SrflEditorDraft } from "../../model/editor-draft.types";
import { SrflEditorStep } from "../../model/editor-state.types";
import { toScientificDraft } from "../../model/mappers";
import { validateAll, validateStep } from "../../model/validation";
import {
  SrflEvidenceProvider,
  useEvidenceActivity,
} from "../evidence/SrflEvidence";
import { AdjacenciesStep } from "./AdjacenciesStep";
import { AdvancedConfigurationStep } from "./AdvancedConfigurationStep";
import { CriteriaStep } from "./CriteriaStep";
import { DesignsStep } from "./DesignsStep";
import { RelationsStep } from "./RelationsStep";
import { ReviewStep } from "./ReviewStep";
import { StationsStep } from "./StationsStep";
import { StudyInformationStep } from "./StudyInformationStep";

const STEPS = [
  { id: SrflEditorStep.Information, label: "Información" },
  { id: SrflEditorStep.Stations, label: "Estaciones" },
  { id: SrflEditorStep.Criteria, label: "Criterios" },
  { id: SrflEditorStep.Relations, label: "Datos de relaciones" },
  { id: SrflEditorStep.Adjacencies, label: "Adyacencias" },
  { id: SrflEditorStep.Designs, label: "Diseños" },
  { id: SrflEditorStep.AdvancedConfiguration, label: "Avanzado" },
  { id: SrflEditorStep.Review, label: "Revisión" },
] as const;

function WizardContent({
  host,
  draft,
  revision,
  onChange,
  onExit,
  onExecute,
}: {
  host: DomainUiHost;
  draft: SrflEditorDraft;
  revision: number;
  onChange: (draft: SrflEditorDraft) => void;
  onExit: () => void;
  onExecute: (
    draft: SingleRowFacilityLayoutDraftV2 | SingleRowFacilityLayoutDraftV21,
    saveAsTemplate: boolean,
  ) => void;
}) {
  const pending = useEvidenceActivity();
  const latestRevision = useRef(revision);
  latestRevision.current = revision;
  const validationRequest = useRef(0);
  const [step, setStep] = useState(SrflEditorStep.Information);
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [highestEnabledIndex, setHighestEnabledIndex] = useState(0);
  const [saveAsTemplate, setSaveAsTemplate] = useState(false);
  const [estimate, setEstimate] = useState<number | string | null>(null);
  const [validatedRevision, setValidatedRevision] = useState<number | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [remoteError, setRemoteError] = useState<string | null>(null);
  const validated = validatedRevision === revision && pending === 0;
  const validateReview = async () => {
    const request = ++validationRequest.current;
    const local = validateAll(draft);
    setErrors(local);
    setRemoteError(null);
    if (local.length > 0) {
      setValidatedRevision(null);
      return;
    }
    setBusy(true);
    try {
      const scientific = toScientificDraft(draft);
      await host.validateStudy(scientific);
      await host.validateForest(scientific);
      const result = await host.estimateCombinations(scientific);
      if (
        request === validationRequest.current &&
        latestRevision.current === revision
      ) {
        setEstimate(result.theoretical_combinations);
        setValidatedRevision(revision);
      }
    } catch (reason) {
      if (request === validationRequest.current) {
        setValidatedRevision(null);
        setRemoteError(String(reason));
      }
    } finally {
      if (request === validationRequest.current) setBusy(false);
    }
  };
  useEffect(() => {
    if (
      step === SrflEditorStep.Review &&
      pending === 0 &&
      validatedRevision !== revision
    )
      void validateReview();
  }, [step, revision, pending]);
  const index = STEPS.findIndex((item) => item.id === step);
  const next = STEPS[index + 1]?.id;
  const previous = STEPS[index - 1]?.id;
  const errorsThrough = (lastIndex: number) =>
    STEPS.slice(0, lastIndex + 1).flatMap((item) =>
      validateStep(draft, item.id),
    );
  const selectStep = (nextStep: SrflEditorStep) => {
    if (pending > 0) return;
    const nextIndex = STEPS.findIndex((item) => item.id === nextStep);
    if (nextIndex > highestEnabledIndex) return;
    if (nextIndex > index) {
      const found = errorsThrough(index);
      setErrors(found);
      if (found.length > 0) return;
    }
    setErrors([]);
    setRemoteError(null);
    setStep(nextStep);
  };
  const goNext = async () => {
    if (next === undefined) return;
    const found = errorsThrough(index);
    setErrors(found);
    setRemoteError(null);
    if (found.length > 0) return;
    if (step === SrflEditorStep.Designs) {
      setBusy(true);
      try {
        await host.validateForest(toScientificDraft(draft));
      } catch (reason) {
        setRemoteError(String(reason));
        return;
      } finally {
        setBusy(false);
      }
    }
    setHighestEnabledIndex((value) => Math.max(value, index + 1));
    setStep(next);
  };
  return (
    <main className="srfl-page">
      <PageHeader
        eyebrow={`Nuevo estudio · SRFL ${draft.schemaVersion}`}
        title={draft.study.title || "Experimento sin título"}
        description="Completá cada etapa antes de preparar."
        actions={
          <Button variant={ButtonVariant.Ghost} onClick={onExit}>
            Salir
          </Button>
        }
      />
      <Wizard
        items={STEPS}
        current={step}
        highestEnabledIndex={highestEnabledIndex}
        onSelect={selectStep}
      />
      <div className="srfl-wizard-actions">
        {previous !== undefined && (
          <ActionButton
            action="previous"
            label="Anterior"
            variant={ButtonVariant.Secondary}
            onClick={() => selectStep(previous)}
          />
        )}
        <span />
        {next !== undefined && (
          <ActionButton
            action="next"
            label={busy ? "Comprobando…" : "Siguiente"}
            loading={busy}
            onClick={() => void goNext()}
            disabled={busy || pending > 0}
          />
        )}
      </div>
      {errors.length > 0 && (
        <div role="alert">
          <ul>
            {errors.map((error) => (
              <li key={`${error.field}-${error.message}`}>{error.message}</li>
            ))}
          </ul>
        </div>
      )}
      {remoteError !== null && <p role="alert">{remoteError}</p>}
      {step === SrflEditorStep.Information && (
        <StudyInformationStep draft={draft} onChange={onChange} />
      )}
      {step === SrflEditorStep.Criteria && (
        <CriteriaStep host={host} draft={draft} onChange={onChange} />
      )}
      {step === SrflEditorStep.Stations && (
        <StationsStep draft={draft} onChange={onChange} />
      )}
      {step === SrflEditorStep.Relations && (
        <RelationsStep draft={draft} onChange={onChange} />
      )}
      {step === SrflEditorStep.Adjacencies && (
        <AdjacenciesStep draft={draft} onChange={onChange} />
      )}
      {step === SrflEditorStep.Designs && (
        <DesignsStep draft={draft} onChange={onChange} />
      )}
      {step === SrflEditorStep.AdvancedConfiguration && (
        <AdvancedConfigurationStep draft={draft} onChange={onChange} />
      )}
      {step === SrflEditorStep.Review && (
        <ReviewStep
          draft={draft}
          estimate={estimate}
          validated={validated}
          busy={busy || pending > 0}
          error={remoteError}
          template={saveAsTemplate}
          onTemplateChange={setSaveAsTemplate}
          onExecute={() => onExecute(toScientificDraft(draft), saveAsTemplate)}
        />
      )}
    </main>
  );
}
export function ExperimentWizard(props: Parameters<typeof WizardContent>[0]) {
  return (
    <SrflEvidenceProvider
      key={props.draft.study.id}
      draft={props.draft}
      onChange={props.onChange}
      service={props.host.attachments}
    >
      <WizardContent {...props} />
    </SrflEvidenceProvider>
  );
}
