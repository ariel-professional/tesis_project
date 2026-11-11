import type {
  DomainUiHost,
  SingleRowFacilityLayoutDomainRun,
  SingleRowFacilityLayoutDraft,
  SingleRowFacilityLayoutResult,
} from "@domain-ui-sdk";
import { BackendConnectionState } from "@domain-ui-sdk";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { executionReducer, INITIAL_EXECUTION_STATE } from "../model/execution-reducer";
import { ExecutionActionKind, ExecutionLifecycle, ExecutionPhase } from "../model/execution-state.types";

function message(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

export function useSrflExecution(host: DomainUiHost) {
  const [state, dispatch] = useReducer(executionReducer, INITIAL_EXECUTION_STATE);
  const [result, setResult] = useState<SingleRowFacilityLayoutResult | null>(null);
  const [cancellationDelayed, setCancellationDelayed] = useState(false);
  const reconciledAfterConnection = useRef(false);
  const terminalReconciledRun = useRef<string | null>(null);

  const reconcile = useCallback(async (runId: string) => {
    const manifest = await host.getDomainRun<SingleRowFacilityLayoutDomainRun>(runId);
    dispatch({ type: ExecutionActionKind.Reconciled, manifest });
    return manifest;
  }, [host]);

  useEffect(() => {
    if (state.operationId === null) return;
    return host.subscribe(state.operationId, (event) => {
      dispatch({ type: ExecutionActionKind.EventReceived, event });
    });
  }, [host, state.operationId]);

  useEffect(() => host.subscribeBackendState((event) => {
    dispatch({
      type: ExecutionActionKind.BackendChanged,
      state: event.state,
      interruptedOperationIds: event.interruptedOperationIds,
    });
  }), [host]);

  useEffect(() => {
    if (!state.needsReconciliation || state.domainRunId === null) return;
    void reconcile(state.domainRunId).catch((reason: unknown) => {
      dispatch({ type: ExecutionActionKind.Failed, error: message(reason) });
    });
  }, [reconcile, state.domainRunId, state.needsReconciliation]);

  useEffect(() => {
    if (
      state.domainRunId === null
      || state.activeCase === null
      || state.activeCase.ordinal <= 1
      || state.lifecycle !== ExecutionLifecycle.Running
    ) return;
    void reconcile(state.domainRunId).catch((reason: unknown) => {
      dispatch({ type: ExecutionActionKind.Failed, error: message(reason) });
    });
  }, [reconcile, state.activeCase?.ordinal, state.domainRunId, state.lifecycle]);

  useEffect(() => {
    if (state.backend !== BackendConnectionState.Connected) {
      reconciledAfterConnection.current = false;
      return;
    }
    if (
      state.lifecycle !== ExecutionLifecycle.Interrupted
      || state.domainRunId === null
      || reconciledAfterConnection.current
    ) return;
    reconciledAfterConnection.current = true;
    void reconcile(state.domainRunId).catch(() => undefined);
  }, [reconcile, state.backend, state.domainRunId, state.lifecycle]);

  useEffect(() => {
    if (
      state.domainRunId === null
      || terminalReconciledRun.current === state.domainRunId
      || ![ExecutionLifecycle.Cancelled, ExecutionLifecycle.Failed].includes(state.lifecycle)
    ) return;
    terminalReconciledRun.current = state.domainRunId;
    void reconcile(state.domainRunId).catch(() => undefined);
  }, [reconcile, state.domainRunId, state.lifecycle]);

  useEffect(() => {
    if (state.lifecycle !== ExecutionLifecycle.Cancelling || state.domainRunId === null) {
      setCancellationDelayed(false);
      return;
    }
    let polling = false;
    const runId = state.domainRunId;
    const poll = () => {
      if (polling) return;
      polling = true;
      void reconcile(runId).catch(() => undefined).finally(() => { polling = false; });
    };
    poll();
    const interval = window.setInterval(poll, 1000);
    const delayed = window.setTimeout(() => setCancellationDelayed(true), 5000);
    return () => {
      window.clearInterval(interval);
      window.clearTimeout(delayed);
    };
  }, [reconcile, state.domainRunId, state.lifecycle]);

  useEffect(() => {
    if (
      state.lifecycle !== ExecutionLifecycle.Completed
      || state.phase === ExecutionPhase.LoadingResult
      || state.domainRunId === null
      || result !== null
    ) return;
    dispatch({ type: ExecutionActionKind.ResultLoading });
    const runId = state.domainRunId;
    const load = async () => {
      let lastError: unknown = null;
      for (let attempt = 0; attempt < 5; attempt += 1) {
        try {
          setResult(await host.getConfirmedResult<SingleRowFacilityLayoutResult>(runId));
          return;
        } catch (reason) {
          lastError = reason;
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
        }
      }
      dispatch({ type: ExecutionActionKind.Failed, error: message(lastError) });
    };
    void load();
  }, [host, result, state.domainRunId, state.lifecycle, state.phase]);

  const start = async (draft: SingleRowFacilityLayoutDraft, saveAsTemplate = false) => {
    dispatch({ type: ExecutionActionKind.Reset });
    terminalReconciledRun.current = null;
    setResult(null);
    try {
      if (saveAsTemplate) await host.saveTemplate(draft);
      const prepared = await host.prepareStudy(draft);
      const accepted = await host.startDomainRun(prepared.domain_experiment_id);
      dispatch({
        type: ExecutionActionKind.Accepted,
        operationId: accepted.operation_id,
        domainRunId: accepted.domain_run_id,
        resuming: false,
      });
      return true;
    } catch (reason) {
      dispatch({ type: ExecutionActionKind.Failed, error: message(reason) });
      return false;
    }
  };

  const resume = async (runId: string) => {
    dispatch({ type: ExecutionActionKind.Reset });
    terminalReconciledRun.current = null;
    setResult(null);
    try {
      const manifest = await host.getDomainRun<SingleRowFacilityLayoutDomainRun>(runId);
      const accepted = await host.resumeDomainRun(runId);
      dispatch({
        type: ExecutionActionKind.Accepted,
        operationId: accepted.operation_id,
        domainRunId: accepted.domain_run_id,
        resuming: true,
        manifest,
      });
      return true;
    } catch (reason) {
      dispatch({ type: ExecutionActionKind.Failed, error: message(reason) });
      return false;
    }
  };

  const cancel = async () => {
    if (
      state.domainRunId === null
      || state.lifecycle === ExecutionLifecycle.Cancelling
      || state.lifecycle === ExecutionLifecycle.Cancelled
    ) return;
    dispatch({ type: ExecutionActionKind.CancellationRequested });
    try {
      await host.cancelDomainRun(state.domainRunId);
    } catch (reason) {
      dispatch({ type: ExecutionActionKind.Failed, error: message(reason) });
    }
  };

  const openResult = async (runId: string) => {
    try {
      setResult(await host.getConfirmedResult<SingleRowFacilityLayoutResult>(runId));
      return null;
    } catch (reason) {
      const error = message(reason);
      dispatch({ type: ExecutionActionKind.Failed, error });
      return error;
    }
  };

  const openRun = async (runId: string, status: string) => {
    if (status === "completed") {
      const error = await openResult(runId);
      return error === null
        ? { opened: true, result: true }
        : { opened: false, result: true, error };
    }
    if (state.domainRunId === runId && state.operationId !== null) return { opened: true, result: false };
    try {
      const manifest = await host.getDomainRun<SingleRowFacilityLayoutDomainRun>(runId);
      setResult(null);
      dispatch({ type: ExecutionActionKind.Inspected, manifest });
      return { opened: true, result: false };
    } catch (reason) {
      dispatch({ type: ExecutionActionKind.Failed, error: message(reason) });
      return { opened: false, result: false, error: message(reason) };
    }
  };

  return { state, result, cancellationDelayed, start, resume, cancel, openRun };
}
