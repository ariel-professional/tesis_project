import {
  Button,
  ButtonVariant,
  ActionButton,
  MetricCard,
  PageHeader,
  Panel,
  ProgressBar,
  SwitchField,
} from "@domain-ui-kit";
import { BackendConnectionState } from "@domain-ui-sdk";
import { useState } from "react";
import {
  CoreStage,
  ExecutionLifecycle,
  type ExecutionState,
  type LargeProgressValue,
} from "../../model/execution-state.types";
import { RunStatusChip } from "../RunStatusChip";

const CORE_STAGES = Object.values(CoreStage);
const STAGE_LABELS: Record<CoreStage, string> = {
  [CoreStage.DefineExperiment]: "Verificando la definición del experimento",
  [CoreStage.LoadOrGenerateInstance]: "Materializando el caso",
  [CoreStage.ValidateInstanceEdges]: "Validando las restricciones",
  [CoreStage.ValidateLinearForest]: "Validando la estructura lineal",
  [CoreStage.AnalyzeStructure]: "Analizando la estructura",
  [CoreStage.RunExactMethod]: "Ejecutando el método exacto",
  [CoreStage.RunReferenceMethod]: "Ejecutando el método de referencia",
  [CoreStage.CompareResults]: "Comparando resultados",
  [CoreStage.CollectMetrics]: "Reuniendo métricas",
  [CoreStage.ExportReport]: "Exportando el reporte",
};

function integer(value: LargeProgressValue): bigint {
  return BigInt(value);
}

function formatted(value: LargeProgressValue): string {
  return integer(value).toLocaleString("es-AR");
}

function percentage(completed: LargeProgressValue, total: LargeProgressValue | null): number {
  if (total === null || integer(total) <= 0n) return 0;
  const basisPoints = integer(completed) * 10_000n / integer(total);
  return Number(basisPoints) / 100;
}

function casePercentage(state: ExecutionState): number {
  const active = state.activeCase;
  if (active?.stage === null || active === null) return 0;
  const ordinal = CORE_STAGES.indexOf(active.stage);
  if (ordinal < 0) return 0;
  const stageFraction = active.stageTotal !== null && active.stageTotal > 0
    ? Math.max(0, Math.min(1, active.stageCompleted / active.stageTotal))
    : 0;
  return ((ordinal + stageFraction) / CORE_STAGES.length) * 100;
}

function executionTitle(lifecycle: ExecutionLifecycle): string {
  if (lifecycle === ExecutionLifecycle.Cancelling) return "Cancelando ejecución";
  if (lifecycle === ExecutionLifecycle.Running) return "Procesando el experimento";
  return "Detalle de la ejecución";
}

export function ExecutionProgress({
  state,
  cancellationDelayed,
  onCancel,
  onResume,
  onHome,
  template,
  templateBusy,
  onTemplateChange,
}: {
  state: ExecutionState;
  cancellationDelayed: boolean;
  onCancel: () => void;
  onResume: () => void | Promise<void>;
  onHome: () => void;
  template?: boolean;
  templateBusy?: boolean;
  onTemplateChange?: (enabled: boolean) => void;
}) {
  const [resuming, setResuming] = useState(false);
  const paused = state.lifecycle === ExecutionLifecycle.Cancelling;
  const live = state.lifecycle === ExecutionLifecycle.Running
    || state.lifecycle === ExecutionLifecycle.Cancelling;
  const overallValue = percentage(state.overallCompleted, state.overallTotal);
  const overallText = state.overallTotal === null
    ? live ? `${formatted(state.overallCompleted)} evaluadas` : "Total no disponible"
    : `${formatted(state.overallCompleted)} / ${formatted(state.overallTotal)} · ${overallValue.toFixed(2)} %`;
  const stageLabel = state.activeCase?.stage === null || state.activeCase === null
    ? "Preparando las etapas CORE"
    : STAGE_LABELS[state.activeCase.stage];
  const resumable = state.lifecycle === ExecutionLifecycle.Cancelled
    || state.lifecycle === ExecutionLifecycle.Failed
    || state.lifecycle === ExecutionLifecycle.Interrupted;
  const resume = async () => {
    if (resuming) return;
    setResuming(true);
    try { await onResume(); }
    finally { setResuming(false); }
  };
  const cancellable = state.lifecycle === ExecutionLifecycle.Running
    || state.lifecycle === ExecutionLifecycle.Interrupted;
  const headerActions = <div className="srfl-header-actions">
    {(resumable || state.lifecycle === ExecutionLifecycle.Completed) && <Button variant={ButtonVariant.Secondary} onClick={onHome}>Volver al inicio</Button>}
    {resumable && <ActionButton action="resume" label={resuming ? "Reanudando…" : "Reanudar"} loading={resuming} onClick={() => void resume()} />}
  </div>;

  return <main className="srfl-page">
    <PageHeader
      eyebrow="Ejecución agrupada"
      title={executionTitle(state.lifecycle)}
      status={<RunStatusChip status={state.lifecycle} />}
      description="Cada combinación válida se confirma y ejecuta completamente antes de generar la siguiente."
      actions={headerActions}
    />
    {state.backend !== BackendConnectionState.Connected && <div className="srfl-execution-notice">
      {state.backend === BackendConnectionState.Restarting ? "Reconectando con el backend…" : "Se perdió la conexión con el backend."}
    </div>}
    {state.domainRunId !== null && onTemplateChange !== undefined && <Panel><SwitchField label="Guardar como plantilla" description="Permite reutilizar la configuración de esta ejecución." checked={template ?? false} disabled={templateBusy} onChange={onTemplateChange} /></Panel>}

    <Panel className="srfl-execution-panel">
      <div className="srfl-execution-run">Run <code>{state.domainRunId ?? "reservando…"}</code></div>
      <ProgressBar
        label="Combinaciones evaluadas"
        value={overallValue}
        valueText={overallText}
        indeterminate={live && state.overallTotal === null}
        paused={paused}
      />
      <div className="srfl-execution-metrics">
        <MetricCard label="Casos CORE confirmados" value={String(state.confirmedCases)} />
        <MetricCard label="Casos CORE completados" value={String(state.completedCases)} />
        <MetricCard label="Casos CORE fallidos" value={String(state.failedCases)} />
        <MetricCard label="Caso activo" value={state.activeCase === null ? "—" : `#${state.activeCase.ordinal}`} />
      </div>
    </Panel>

    <Panel className="srfl-current-case">
      <div className="srfl-current-case__heading">
        <div>
          <span className="ui-eyebrow">{live ? "Caso CORE actual" : "Último caso CORE"}</span>
          <h2>{state.activeCase === null ? paused ? "Cancelación solicitada" : "Esperando el primer caso válido" : `Caso ${state.activeCase.ordinal}`}</h2>
        </div>
        {state.activeCase !== null && <RunStatusChip status={state.lifecycle} />}
      </div>
      <p>{state.activeCase?.description ?? "El dominio está evaluando y podando combinaciones."}</p>
      {!live && (state.activeCase === null || state.activeCase.stage === null)
        ? <p className="srfl-execution-notice">No hay una etapa CORE activa. Se muestran los últimos datos confirmados antes de que la ejecución terminara.</p>
        : paused && (state.activeCase === null || state.activeCase.stage === null)
        ? <p className="srfl-cancellation-message">La cancelación fue solicitada antes de iniciar una etapa CORE. Esperando la confirmación durable.</p>
        : <ProgressBar
            label={stageLabel}
            value={casePercentage(state)}
            valueText={state.activeCase?.stage === null || state.activeCase === null
              ? undefined
              : `Etapa ${CORE_STAGES.indexOf(state.activeCase.stage) + 1} de ${CORE_STAGES.length}`}
            indeterminate={state.activeCase === null || state.activeCase.stage === null}
            paused={paused}
          />}
      {paused && <p className="srfl-cancellation-message">
        No se iniciarán casos nuevos. Estamos esperando que CORE confirme el cierre del caso actual.
      </p>}
      {cancellationDelayed && <p className="srfl-cancellation-message">
        CORE continúa cerrando la etapa actual. La aplicación seguirá consultando el estado durable.
      </p>}
    </Panel>

    {state.error !== null && <p className="srfl-error" role="alert">{state.error}</p>}
    <div className="srfl-actions">
      {cancellable && <ActionButton action="cancel" label="Cancelar" variant={ButtonVariant.Danger} onClick={onCancel} />}
      {paused && <ActionButton action="cancel" label="Cancelando…" variant={ButtonVariant.Danger} loading />}
    </div>

    <details className="srfl-technical-progress">
      <summary>Detalles técnicos</summary>
      <dl>
        <dt>Operación</dt><dd><code>{state.operationId ?? "—"}</code></dd>
        <dt>CORE activo</dt><dd><code>{state.activeCase?.coreRunId ?? "—"}</code></dd>
        <dt>Última secuencia</dt><dd>{state.lastSequence}</dd>
      </dl>
      <div className="srfl-event-log">
        {state.eventLog.map((event) => <code key={`${event.operation_id}-${event.sequence}`}>
          {event.sequence}. {event.event}
        </code>)}
      </div>
    </details>
  </main>;
}
