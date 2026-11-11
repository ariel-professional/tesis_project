import { contextBridge, ipcRenderer } from "electron";

const invoke = (channel: string, params: Record<string, unknown>) =>
  ipcRenderer.invoke(channel, params) as Promise<{ operation_id: string | null; result: unknown }>;

const desktopApi = {
  beginAttachment: (name: string, media_type: string, size_bytes: number) => invoke("desktop:attachments-begin", { name, media_type, size_bytes }),
  appendAttachment: (upload_id: string, offset: number, data: string) => invoke("desktop:attachments-append", { upload_id, offset, data }),
  finishAttachment: (upload_id: string) => invoke("desktop:attachments-finish", { upload_id }),
  abortAttachment: (upload_id: string) => invoke("desktop:attachments-abort", { upload_id }),
  readAttachment: (sha256: string, offset: number, length: number) => invoke("desktop:attachments-read", { sha256, offset, length }),
  getStudyDocumentation: (domain_experiment_id: string) => invoke("desktop:study-documentation", { domain_experiment_id }),
  openEvidenceLink: (url: string) => ipcRenderer.invoke("desktop:evidence-open-link", url) as Promise<void>,
  listDomains: () => invoke("desktop:domains-list", {}),
  getLayoutDecisionCriteria: () => invoke("desktop:decision-criteria", {}),
  listTemplates: () => invoke("desktop:templates-list", {}),
  openDefinitionFile: () => ipcRenderer.invoke("desktop:definition-open") as Promise<unknown | null>,
  loadTemplate: (templateId: string) => invoke("desktop:templates-load", { template_id: templateId }),
  saveTemplate: (draft: unknown) => invoke("desktop:templates-save", { draft }),
  setRunTemplate: (domainRunId: string, enabled: boolean) =>
    invoke("desktop:templates-set-for-run", { domain_run_id: domainRunId, enabled }),
  validateStudy: (draft: unknown) => invoke("desktop:study-validate", { draft }),
  prepareStudy: (draft: unknown) => invoke("desktop:study-prepare", { draft }),
  validateForest: (draft: unknown) => invoke("desktop:layout-validate-forest", { draft }),
  estimateCombinations: (draft: unknown) => invoke("desktop:layout-estimate", { draft }),
  startDomainRun: (domainExperimentId: string) =>
    invoke("desktop:domain-run-start", { domain_experiment_id: domainExperimentId }),
  cancelDomainRun: (domainRunId: string, reason?: string) =>
    invoke("desktop:domain-run-cancel", { domain_run_id: domainRunId, reason: reason ?? null }),
  resumeDomainRun: (domainRunId: string) =>
    invoke("desktop:domain-run-resume", { domain_run_id: domainRunId }),
  getDomainRun: (domainRunId: string) =>
    invoke("desktop:domain-run-status", { domain_run_id: domainRunId }),
  listDomainRuns: () => invoke("desktop:domain-run-list", {}),
  deleteDomainRun: (domainRunId: string) =>
    invoke("desktop:domain-run-delete", { domain_run_id: domainRunId }),
  getDomainRunResult: (domainRunId: string) =>
    invoke("desktop:domain-run-result", { domain_run_id: domainRunId }),
  getDomainRunCasePage: (params: Record<string, unknown>) => invoke("desktop:domain-run-case-page", params),
  getDomainRunCaseDetail: (params: Record<string, unknown>) => invoke("desktop:domain-run-case-detail", params),
  getDomainRunDominators: (params: Record<string, unknown>) => invoke("desktop:domain-run-dominators", params),
  getDomainRunFrontier: (params: Record<string, unknown>) => invoke("desktop:domain-run-frontier", params),
  getDomainRunPlotPoints: (params: Record<string, unknown>) => invoke("desktop:domain-run-plot-points", params),
  getDomainRunPlotProjection: (params: Record<string, unknown>) => invoke("desktop:domain-run-plot-projection", params),
  getResultMetrics: (params: Record<string, unknown>) => invoke("desktop:domain-run-metrics", params),
  onOperationEvent: (listener: (event: unknown) => void) => {
    const wrapped = (_event: Electron.IpcRendererEvent, payload: unknown) => listener(payload);
    ipcRenderer.on("desktop:operation-event", wrapped);
    return () => ipcRenderer.removeListener("desktop:operation-event", wrapped);
  },
  onBackendState: (listener: (event: unknown) => void) => {
    const wrapped = (_event: Electron.IpcRendererEvent, payload: unknown) => listener(payload);
    ipcRenderer.on("desktop:backend-state", wrapped);
    return () => ipcRenderer.removeListener("desktop:backend-state", wrapped);
  },
};

contextBridge.exposeInMainWorld("desktopApi", desktopApi);
