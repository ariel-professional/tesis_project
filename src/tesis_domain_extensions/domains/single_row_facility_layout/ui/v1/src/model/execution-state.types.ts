import type {
  BackendConnectionState,
  DomainOperationEvent,
  SingleRowFacilityLayoutDomainRun,
} from "@domain-ui-sdk";

export enum ExecutionLifecycle {
  Running = "running",
  Cancelling = "cancelling",
  Completed = "completed",
  Cancelled = "cancelled",
  Failed = "failed",
  Interrupted = "interrupted",
}

export enum ExecutionPhase {
  Generating = "generating",
  CoreCase = "core-case",
  LoadingResult = "loading-result",
}

export enum CoreStage {
  DefineExperiment = "define_experiment",
  LoadOrGenerateInstance = "load_or_generate_instance",
  ValidateInstanceEdges = "validate_instance_edges",
  ValidateLinearForest = "validate_linear_forest",
  AnalyzeStructure = "analyze_structure",
  RunExactMethod = "run_exact_method",
  RunReferenceMethod = "run_reference_method",
  CompareResults = "compare_results",
  CollectMetrics = "collect_metrics",
  ExportReport = "export_report",
}

export type LargeProgressValue = number | string;

export type ActiveCoreCase = {
  readonly ordinal: number;
  readonly description: string;
  readonly coreRunId: string;
  readonly stage: CoreStage | null;
  readonly stageCompleted: number;
  readonly stageTotal: number | null;
};

export type ExecutionState = {
  readonly lifecycle: ExecutionLifecycle;
  readonly phase: ExecutionPhase;
  readonly backend: BackendConnectionState;
  readonly operationId: string | null;
  readonly domainRunId: string | null;
  readonly resuming: boolean;
  readonly lastSequence: number;
  readonly needsReconciliation: boolean;
  readonly overallCompleted: LargeProgressValue;
  readonly overallTotal: LargeProgressValue | null;
  readonly activeCase: ActiveCoreCase | null;
  readonly confirmedCases: number;
  readonly completedCases: number;
  readonly failedCases: number;
  readonly error: string | null;
  readonly eventLog: readonly DomainOperationEvent[];
};

export enum ExecutionActionKind {
  Reset = "reset",
  Inspected = "inspected",
  Accepted = "accepted",
  EventReceived = "event-received",
  CancellationRequested = "cancellation-requested",
  BackendChanged = "backend-changed",
  Reconciled = "reconciled",
  ResultLoading = "result-loading",
  Failed = "failed",
}

export type ExecutionAction =
  | { type: ExecutionActionKind.Reset }
  | { type: ExecutionActionKind.Inspected; manifest: SingleRowFacilityLayoutDomainRun }
  | {
      type: ExecutionActionKind.Accepted;
      operationId: string;
      domainRunId: string;
      resuming: boolean;
      manifest?: SingleRowFacilityLayoutDomainRun;
    }
  | { type: ExecutionActionKind.EventReceived; event: DomainOperationEvent }
  | { type: ExecutionActionKind.CancellationRequested }
  | {
      type: ExecutionActionKind.BackendChanged;
      state: BackendConnectionState;
      interruptedOperationIds: readonly string[];
    }
  | { type: ExecutionActionKind.Reconciled; manifest: SingleRowFacilityLayoutDomainRun }
  | { type: ExecutionActionKind.ResultLoading }
  | { type: ExecutionActionKind.Failed; error: string };
