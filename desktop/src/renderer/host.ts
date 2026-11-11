import { ElectronAttachmentService } from "./attachments";
import type {
  AcceptedOperation,
  BackendStateEvent,
  DomainOperationEvent,
  DomainUiHost,
  TemplateDescriptor,
} from "@domain-ui-sdk";
import {
  assertConfirmedDomainResult,
  resolveTransportedDomainResult,
} from "./gateway-result-transport";

type Observer = (event: DomainOperationEvent) => void;

export class ElectronDomainUiHost implements DomainUiHost {
  readonly attachments = new ElectronAttachmentService();
  private readonly observers = new Map<string, Set<Observer>>();
  private readonly backlog = new Map<string, DomainOperationEvent[]>();
  private readonly backendObservers = new Set<(event: BackendStateEvent) => void>();
  private readonly detachOperationEvents: () => void;
  private readonly detachBackendState: () => void;

  constructor() {
    this.detachOperationEvents = window.desktopApi.onOperationEvent((candidate) => {
      const event = candidate as DomainOperationEvent;
      const listeners = this.observers.get(event.operation_id);
      if (listeners === undefined) {
        const queued = this.backlog.get(event.operation_id) ?? [];
        queued.push(event);
        this.backlog.set(event.operation_id, queued.slice(-1000));
        return;
      }
      for (const listener of listeners) listener(event);
    });
    this.detachBackendState = window.desktopApi.onBackendState((candidate) => {
      const event = candidate as BackendStateEvent;
      for (const observer of this.backendObservers) observer(event);
    });
  }

  dispose(): void {
    void this.attachments.discardStaged();
    this.detachOperationEvents();
    this.detachBackendState();
    this.observers.clear();
    this.backendObservers.clear();
    this.backlog.clear();
  }

  async listTemplates(): Promise<readonly TemplateDescriptor[]> {
    return (await window.desktopApi.listTemplates()).result as readonly TemplateDescriptor[];
  }

  async openDefinitionFile(): Promise<unknown | null> {
    return window.desktopApi.openDefinitionFile();
  }

  async getLayoutDecisionCriteria(): Promise<readonly import("@domain-ui-sdk").DecisionCriterionDescriptor[]> {
    return (await window.desktopApi.getLayoutDecisionCriteria()).result as readonly import("@domain-ui-sdk").DecisionCriterionDescriptor[];
  }

  async loadTemplate<TDraft>(templateId: string): Promise<TDraft> {
    return (await window.desktopApi.loadTemplate(templateId)).result as TDraft;
  }

  async saveTemplate<TDraft>(draft: TDraft): Promise<void> {
    await window.desktopApi.saveTemplate(draft);
  }

  async setRunTemplate(domainRunId: string, enabled: boolean): Promise<void> {
    await window.desktopApi.setRunTemplate(domainRunId, enabled);
  }

  async validateStudy<TDraft>(draft: TDraft): Promise<{ valid: true; draft: TDraft }> {
    return (await window.desktopApi.validateStudy(draft)).result as {
      valid: true;
      draft: TDraft;
    };
  }

  async validateForest<TDraft>(draft: TDraft): Promise<{ valid: true; draft: TDraft }> {
    return (await window.desktopApi.validateForest(draft)).result as {
      valid: true;
      draft: TDraft;
    };
  }

  async estimateCombinations<TDraft>(
    draft: TDraft,
  ): Promise<{ theoretical_combinations: number | string }> {
    return (await window.desktopApi.estimateCombinations(draft)).result as {
      theoretical_combinations: number | string;
    };
  }

  async prepareStudy<TDraft>(draft: TDraft): Promise<{ domain_experiment_id: string }> {
    return (await window.desktopApi.prepareStudy(draft)).result as {
      domain_experiment_id: string;
    };
  }

  async startDomainRun(domainExperimentId: string): Promise<AcceptedOperation> {
    const reply = await window.desktopApi.startDomainRun(domainExperimentId);
    const result = reply.result as { domain_run_id: string };
    if (reply.operation_id === null) throw new Error("El gateway no confirmó la operación.");
    return { operation_id: reply.operation_id, domain_run_id: result.domain_run_id };
  }

  async cancelDomainRun(domainRunId: string, reason?: string): Promise<void> {
    await window.desktopApi.cancelDomainRun(domainRunId, reason);
  }

  async resumeDomainRun(domainRunId: string): Promise<AcceptedOperation> {
    const reply = await window.desktopApi.resumeDomainRun(domainRunId);
    const result = reply.result as { domain_run_id: string };
    if (reply.operation_id === null) throw new Error("El gateway no confirmó la operación.");
    return { operation_id: reply.operation_id, domain_run_id: result.domain_run_id };
  }

  async listDomainRuns(): Promise<readonly unknown[]> {
    return (await window.desktopApi.listDomainRuns()).result as readonly unknown[];
  }

  async deleteDomainRun(domainRunId: string): Promise<{
    deleted_domain_run_id: string;
    deleted_domain_experiment: string | null;
    preserved_template: boolean;
  }> {
    return (await window.desktopApi.deleteDomainRun(domainRunId)).result as {
      deleted_domain_run_id: string;
      deleted_domain_experiment: string | null;
      preserved_template: boolean;
    };
  }

  async getDomainRun<TManifest>(domainRunId: string): Promise<TManifest> {
    return (await window.desktopApi.getDomainRun(domainRunId)).result as TManifest;
  }

  subscribe(operationId: string, observer: Observer): () => void {
    const listeners = this.observers.get(operationId) ?? new Set<Observer>();
    listeners.add(observer);
    this.observers.set(operationId, listeners);
    const queued = this.backlog.get(operationId) ?? [];
    this.backlog.delete(operationId);
    for (const event of queued.sort((left, right) => left.sequence - right.sequence)) {
      observer(event);
    }
    return () => {
      listeners.delete(observer);
      if (listeners.size === 0) this.observers.delete(operationId);
    };
  }

  subscribeBackendState(observer: (event: BackendStateEvent) => void): () => void {
    this.backendObservers.add(observer);
    return () => this.backendObservers.delete(observer);
  }

  async getConfirmedResult<TResult>(domainRunId: string): Promise<TResult> {
    const reply = await window.desktopApi.getDomainRunResult(domainRunId);
    const result = await resolveTransportedDomainResult(reply.result, async (sha256, offset, length) => {
      const chunk = await window.desktopApi.readAttachment(sha256, offset, length);
      return (chunk.result as { data: string }).data;
    });
    assertConfirmedDomainResult(result);
    return result as TResult;
  }

  async getCasePage<T>(params: { domain_run_id: string; design_id: string; order: string; direction: "ascending" | "descending"; page: number }): Promise<T> {
    return (await window.desktopApi.getDomainRunCasePage(params)).result as T;
  }
  async getCaseDetail<T>(params: { domain_run_id: string; case_id: string; equivalent_offset?: number }): Promise<T> {
    return (await window.desktopApi.getDomainRunCaseDetail(params)).result as T;
  }
  async getDominators<T>(params: { domain_run_id: string; case_id: string; cursor?: number }): Promise<T> {
    return (await window.desktopApi.getDomainRunDominators(params)).result as T;
  }
  async getFrontier<T>(params: { domain_run_id: string; design_id: string; cursor?: number }): Promise<T> {
    return (await window.desktopApi.getDomainRunFrontier(params)).result as T;
  }
  async getPlotPoints<T>(params: { domain_run_id: string; design_id: string; x_objective_id: string; y_objective_id: string; cursor?: number }): Promise<T> {
    return (await window.desktopApi.getDomainRunPlotPoints(params)).result as T;
  }
  async getPlotProjection<T>(params: { domain_run_id: string; design_id: string; x_objective_id: string; y_objective_id: string; x_scale: "automatic" | "linear" | "square-root" | "adjusted-log" | "percentile"; y_scale: "automatic" | "linear" | "square-root" | "adjusted-log" | "percentile"; x_log_k: number; y_log_k: number; level: 0 | 1 | 2; section: "groups" | "frontier_positions"; cursor?: number }): Promise<T> {
    return (await window.desktopApi.getDomainRunPlotProjection(params)).result as T;
  }
  async getResultMetrics<T>(params: { domain_run_id: string; metric_id: string; design_id?: string; criterion_id?: string; case_id?: string; cursor?: number }): Promise<T> {
    return (await window.desktopApi.getResultMetrics(params)).result as T;
  }
}
