import { BackendConnectionState, type DomainOperationEvent, type SingleRowFacilityLayoutDomainRun } from "@domain-ui-sdk";
import {
  CoreStage,
  ExecutionActionKind,
  ExecutionLifecycle,
  ExecutionPhase,
  type ExecutionAction,
  type ExecutionState,
} from "./execution-state.types";

const EVENT_LOG_LIMIT = 100;

export const INITIAL_EXECUTION_STATE: ExecutionState = {
  lifecycle: ExecutionLifecycle.Running,
  phase: ExecutionPhase.Generating,
  backend: BackendConnectionState.Connected,
  operationId: null,
  domainRunId: null,
  resuming: false,
  lastSequence: 0,
  needsReconciliation: false,
  overallCompleted: 0,
  overallTotal: null,
  validCases: 0,
  designs: [],
  activeDurationMs: 0,
  activeStartedAt: null,
  lastCheckpointAt: null,
  activeCase: null,
  confirmedCases: 0,
  completedCases: 0,
  failedCases: 0,
  error: null,
  eventLog: [],
};

function isCoreStage(value: string): value is CoreStage {
  return Object.values(CoreStage).some((stage) => stage === value);
}

function terminalLifecycle(status: "completed" | "failed" | "cancelled"): ExecutionLifecycle {
  if (status === "completed") return ExecutionLifecycle.Completed;
  if (status === "cancelled") return ExecutionLifecycle.Cancelled;
  return ExecutionLifecycle.Failed;
}

function manifestLifecycle(
  manifest: SingleRowFacilityLayoutDomainRun,
  current: ExecutionLifecycle,
): ExecutionLifecycle {
  if (manifest.status === "completed") return ExecutionLifecycle.Completed;
  if (manifest.status === "cancelled") return ExecutionLifecycle.Cancelled;
  if (manifest.status === "failed") return ExecutionLifecycle.Failed;
  if (current === ExecutionLifecycle.Cancelling || current === ExecutionLifecycle.Interrupted) {
    return current;
  }
  return ExecutionLifecycle.Running;
}

function currentCaseFromManifest(manifest: SingleRowFacilityLayoutDomainRun) {
  const index = manifest.cases.findIndex((item) => item.attempts.at(-1)?.status !== "completed");
  if (index < 0) return null;
  const item = manifest.cases[index];
  const attempt = item?.attempts.at(-1);
  if (item === undefined || attempt === undefined) return null;
  const origin = item.origins[0];
  const description = origin === undefined
    ? "Caso persistido"
    : origin.added_component_ids.length === 0
      ? "Diseño en evaluación · sin restricciones agregadas"
      : `Diseño en evaluación · ${origin.added_component_ids.length} ${origin.added_component_ids.length === 1 ? "restricción agregada" : "restricciones agregadas"}`;
  return {
    ordinal: index + 1,
    description,
    coreRunId: attempt.core_run_id,
    designId: origin?.design_id ?? null,
    stage: null,
    stageCompleted: 0,
    stageTotal: null,
  };
}

function reconcile(state: ExecutionState, manifest: SingleRowFacilityLayoutDomainRun): ExecutionState {
  const extended = manifest as SingleRowFacilityLayoutDomainRun & { designs?: { design_id: string; design_title: string; theoretical_combinations: number | string }[]; active_duration_ms?: number; active_started_at?: string | null };
  const counts = new Map<string, number>();
  for (const item of manifest.cases) {
    const id = item.origins[0]?.design_id;
    if (id) counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  return {
    ...state,
    lifecycle: manifestLifecycle(manifest, state.lifecycle),
    domainRunId: manifest.domain_run_id,
    overallTotal: manifest.generation.theoretical_combinations,
    overallCompleted: BigInt(manifest.generation.valid_selections) + BigInt(manifest.generation.invalid_combinations) > BigInt(state.overallCompleted) ? String(BigInt(manifest.generation.valid_selections) + BigInt(manifest.generation.invalid_combinations)) : state.overallCompleted,
    validCases: manifest.generation.valid_selections,
    designs: (extended.designs ?? []).map((item) => ({ designId: item.design_id, title: item.design_title, theoretical: item.theoretical_combinations, ownedCases: counts.get(item.design_id) ?? 0 })),
    activeDurationMs: extended.active_duration_ms ?? 0,
    activeStartedAt: extended.active_started_at ?? null,
    lastCheckpointAt: manifest.updated_at,
    confirmedCases: manifest.cases.length,
    completedCases: manifest.cases.filter((item) => item.attempts.at(-1)?.status === "completed").length,
    failedCases: manifest.cases.filter((item) => item.attempts.at(-1)?.status === "failed").length,
    activeCase: currentCaseFromManifest(manifest) ?? state.activeCase,
    needsReconciliation: false,
  };
}

function reduceEvent(state: ExecutionState, event: DomainOperationEvent): ExecutionState {
  if (event.operation_id !== state.operationId || event.sequence <= state.lastSequence) return state;
  const gap = state.lastSequence > 0 && event.sequence !== state.lastSequence + 1;
  const base = {
    ...state,
    lastSequence: event.sequence,
    needsReconciliation: state.needsReconciliation || gap,
    eventLog: [...state.eventLog, event].slice(-EVENT_LOG_LIMIT),
  };
  if (event.event === "terminal") {
    return {
      ...base,
      lifecycle: terminalLifecycle(event.data.status),
    };
  }
  if (event.event === "error") {
    return { ...base, lifecycle: ExecutionLifecycle.Failed, error: event.data.error.message };
  }
  if (state.lifecycle === ExecutionLifecycle.Cancelling) return base;
  if (event.event === "generation_started") {
    return { ...base, lifecycle: ExecutionLifecycle.Running, phase: ExecutionPhase.Generating, overallCompleted: 0, validCases: 0, overallTotal: event.data.total };
  }
  if (event.event === "generation_progress") {
    return { ...base, overallCompleted: event.data.completed, overallTotal: event.data.total, validCases: event.data.valid_selections ?? state.validCases };
  }
  if (event.event === "core_case_started") {
    return {
      ...base,
      phase: ExecutionPhase.CoreCase,
      confirmedCases: Math.max(state.confirmedCases, event.data.ordinal),
      designs: event.data.ordinal > state.confirmedCases && event.data.design_id ? state.designs.map((design) => design.designId === event.data.design_id ? { ...design, ownedCases: design.ownedCases + 1 } : design) : state.designs,
      activeCase: {
        ordinal: event.data.ordinal,
        description: event.data.description,
        coreRunId: event.data.core_run_id,
        designId: event.data.design_id ?? null,
        stage: null,
        stageCompleted: 0,
        stageTotal: null,
      },
    };
  }
  if (event.event === "core_progress") {
    if (state.activeCase === null || state.activeCase.coreRunId !== event.data.core_run_id) return base;
    return {
      ...base,
      phase: ExecutionPhase.CoreCase,
      activeCase: {
        ...state.activeCase,
        stage: isCoreStage(event.data.stage) ? event.data.stage : null,
        stageCompleted: event.data.completed,
        stageTotal: event.data.total,
      },
    };
  }
  return base;
}

export function executionReducer(state: ExecutionState, action: ExecutionAction): ExecutionState {
  switch (action.type) {
    case ExecutionActionKind.Reset:
      return { ...INITIAL_EXECUTION_STATE, backend: state.backend };
    case ExecutionActionKind.Inspected: {
      const inspected = reconcile(
        { ...INITIAL_EXECUTION_STATE, backend: state.backend },
        action.manifest,
      );
      return action.manifest.status === "created" || action.manifest.status === "running"
        ? { ...inspected, lifecycle: ExecutionLifecycle.Interrupted }
        : inspected;
    }
    case ExecutionActionKind.Accepted: {
      const accepted = {
        ...INITIAL_EXECUTION_STATE,
        backend: state.backend,
        lifecycle: ExecutionLifecycle.Running,
        operationId: action.operationId,
        domainRunId: action.domainRunId,
        resuming: action.resuming,
      };
      return action.manifest === undefined ? accepted : reconcile(accepted, action.manifest);
    }
    case ExecutionActionKind.EventReceived:
      return reduceEvent(state, action.event);
    case ExecutionActionKind.CancellationRequested:
      return { ...state, lifecycle: ExecutionLifecycle.Cancelling, error: null };
    case ExecutionActionKind.BackendChanged:
      return {
        ...state,
        backend: action.state,
        lifecycle:
          state.operationId !== null && action.interruptedOperationIds.includes(state.operationId)
            ? ExecutionLifecycle.Interrupted
            : state.lifecycle,
      };
    case ExecutionActionKind.Reconciled:
      return reconcile(state, action.manifest);
    case ExecutionActionKind.ResultLoading:
      return { ...state, phase: ExecutionPhase.LoadingResult };
    case ExecutionActionKind.Failed:
      return { ...state, lifecycle: ExecutionLifecycle.Failed, error: action.error };
  }
}

export function needsStatusReconciliation(
  previousSequence: number,
  event: DomainOperationEvent,
): boolean {
  return previousSequence > 0 && event.sequence > previousSequence + 1;
}
