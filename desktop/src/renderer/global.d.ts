export {};

declare global {
  interface Window {
    desktopApi: {
      beginAttachment(name: string, mediaType: string, sizeBytes: number): Promise<DesktopReply>;
      appendAttachment(uploadId: string, offset: number, data: string): Promise<DesktopReply>;
      finishAttachment(uploadId: string): Promise<DesktopReply>;
      abortAttachment(uploadId: string): Promise<DesktopReply>;
      readAttachment(sha256: string, offset: number, length: number): Promise<DesktopReply>;
      getStudyDocumentation(experimentId: string): Promise<DesktopReply>;
      openEvidenceLink(url: string): Promise<void>;
      listDomains(): Promise<DesktopReply>;
      getLayoutDecisionCriteria(): Promise<DesktopReply>;
      listTemplates(): Promise<DesktopReply>;
      openDefinitionFile(): Promise<unknown | null>;
      loadTemplate(templateId: string): Promise<DesktopReply>;
      saveTemplate(draft: unknown): Promise<DesktopReply>;
      setRunTemplate(domainRunId: string, enabled: boolean): Promise<DesktopReply>;
      validateStudy(draft: unknown): Promise<DesktopReply>;
      prepareStudy(draft: unknown): Promise<DesktopReply>;
      validateForest(draft: unknown): Promise<DesktopReply>;
      estimateCombinations(draft: unknown): Promise<DesktopReply>;
      startDomainRun(domainExperimentId: string): Promise<DesktopReply>;
      cancelDomainRun(domainRunId: string, reason?: string): Promise<DesktopReply>;
      resumeDomainRun(domainRunId: string): Promise<DesktopReply>;
      getDomainRun(domainRunId: string): Promise<DesktopReply>;
      listDomainRuns(): Promise<DesktopReply>;
      deleteDomainRun(domainRunId: string): Promise<DesktopReply>;
      getDomainRunResult(domainRunId: string): Promise<DesktopReply>;
      getDomainRunCasePage(params: Record<string, unknown>): Promise<DesktopReply>;
      getDomainRunCaseDetail(params: Record<string, unknown>): Promise<DesktopReply>;
      getDomainRunDominators(params: Record<string, unknown>): Promise<DesktopReply>;
      getDomainRunFrontier(params: Record<string, unknown>): Promise<DesktopReply>;
      getDomainRunPlotPoints(params: Record<string, unknown>): Promise<DesktopReply>;
      getDomainRunPlotProjection(params: Record<string, unknown>): Promise<DesktopReply>;
      getResultMetrics(params: Record<string, unknown>): Promise<DesktopReply>;
      onOperationEvent(listener: (event: unknown) => void): () => void;
      onBackendState(listener: (event: unknown) => void): () => void;
    };
  }
}

type DesktopReply = { operation_id: string | null; result: unknown };
