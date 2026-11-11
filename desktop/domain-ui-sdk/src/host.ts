import type { AttachmentService } from "./evidence";
import type { BackendStateEvent, DomainOperationEvent } from "./events";
import type { AcceptedOperation } from "./runs";
import type { TemplateDescriptor } from "./templates";

export type DecisionCriterionDescriptor = { id: string; version: "1"; name: string; summary: string; decision_question: string; direction: "maximize" | "minimize"; direction_mode: "fixed" | "per_instance"; repeatable_input: boolean; unit: string; formula: string; evidence: string[]; limitations: string[]; required_inputs: string[] };

export interface DomainUiHost {
  readonly attachments?: AttachmentService;
  listTemplates(): Promise<readonly TemplateDescriptor[]>;
  loadTemplate<TDraft>(templateId: string): Promise<TDraft>;
  saveTemplate<TDraft>(draft: TDraft): Promise<void>;
  setRunTemplate(domainRunId: string, enabled: boolean): Promise<void>;
  openDefinitionFile(): Promise<unknown | null>;
  getLayoutDecisionCriteria?(): Promise<readonly DecisionCriterionDescriptor[]>;
  validateStudy<TDraft>(draft: TDraft): Promise<{ valid: true; draft: TDraft }>;
  validateForest<TDraft>(draft: TDraft): Promise<{ valid: true; draft: TDraft }>;
  estimateCombinations<TDraft>(draft: TDraft): Promise<{ theoretical_combinations: number | string }>;
  prepareStudy<TDraft>(draft: TDraft): Promise<{ domain_experiment_id: string }>;
  startDomainRun(domainExperimentId: string): Promise<AcceptedOperation>;
  cancelDomainRun(domainRunId: string, reason?: string): Promise<void>;
  resumeDomainRun(domainRunId: string): Promise<AcceptedOperation>;
  listDomainRuns(): Promise<readonly unknown[]>;
  deleteDomainRun(domainRunId: string): Promise<{
    deleted_domain_run_id: string;
    deleted_domain_experiment: string | null;
    preserved_template: boolean;
  }>;
  getDomainRun<TManifest>(domainRunId: string): Promise<TManifest>;
  subscribe(operationId: string, observer: (event: DomainOperationEvent) => void): () => void;
  subscribeBackendState(observer: (event: BackendStateEvent) => void): () => void;
  getConfirmedResult<TResult>(domainRunId: string): Promise<TResult>;
  getCasePage?<T>(params: { domain_run_id: string; design_id: string; order: string; direction: "ascending" | "descending"; page: number }): Promise<T>;
  getCaseDetail?<T>(params: { domain_run_id: string; case_id: string; equivalent_offset?: number }): Promise<T>;
  getDominators?<T>(params: { domain_run_id: string; case_id: string; cursor?: number }): Promise<T>;
  getFrontier?<T>(params: { domain_run_id: string; design_id: string; cursor?: number }): Promise<T>;
  getPlotPoints?<T>(params: { domain_run_id: string; design_id: string; x_objective_id: string; y_objective_id: string; cursor?: number }): Promise<T>;
  getPlotProjection?<T>(params: { domain_run_id: string; design_id: string; x_objective_id: string; y_objective_id: string; x_scale: "automatic" | "linear" | "square-root" | "adjusted-log" | "percentile"; y_scale: "automatic" | "linear" | "square-root" | "adjusted-log" | "percentile"; x_log_k: number; y_log_k: number; level: 0 | 1 | 2; section: "groups" | "frontier_positions"; cursor?: number }): Promise<T>;
  getResultMetrics<T>(params: { domain_run_id: string; metric_id: string; design_id?: string; criterion_id?: string; case_id?: string; cursor?: number }): Promise<T>;
}
