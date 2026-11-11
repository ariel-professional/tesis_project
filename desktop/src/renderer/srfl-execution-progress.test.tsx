import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { BackendConnectionState } from "@domain-ui-sdk";
import { afterEach, expect, test } from "vitest";
import { ExecutionProgress } from "@srfl-ui/components/execution/ExecutionProgress";
import { CoreStage, ExecutionLifecycle, ExecutionPhase, type ExecutionState } from "@srfl-ui/model/execution-state.types";

afterEach(cleanup);

test("execution progress renders the general and active CORE case bars", () => {
  const state: ExecutionState = {
    lifecycle: ExecutionLifecycle.Running,
    phase: ExecutionPhase.CoreCase,
    backend: BackendConnectionState.Connected,
    operationId: "operation-1",
    domainRunId: "domain-run-1",
    resuming: false,
    lastSequence: 4,
    needsReconciliation: false,
    overallCompleted: 10,
    overallTotal: 100,
    validCases: 4, designs: [{ designId: "d1", title: "Diseño 1", theoretical: 100, ownedCases: 1 }], activeDurationMs: 0, activeStartedAt: null, lastCheckpointAt: null,
    activeCase: {
      ordinal: 1,
      description: "diseño d1; añadidos: c1",
      coreRunId: "core-run-1",
      designId: "d1",
      stage: CoreStage.ValidateLinearForest,
      stageCompleted: 1,
      stageTotal: 1,
    },
    confirmedCases: 1,
    completedCases: 0,
    failedCases: 0,
    error: null,
    eventLog: [],
  };

  render(<ExecutionProgress state={state} cancellationDelayed={false} onCancel={() => undefined} onResume={() => undefined} onHome={() => undefined} />);

  expect(screen.getByRole("progressbar", { name: "Progreso general" }).getAttribute("aria-valuenow")).toBe("10");
  expect(screen.getByRole("progressbar", { name: "Validando la estructura lineal" }).getAttribute("aria-valuenow")).toBe("40");
  expect(screen.getByText("10.00 %")).toBeTruthy();
  expect(screen.getByText("Caso 1")).toBeTruthy();
  expect(screen.getByText("Casos válidos")).toBeTruthy();
  expect(screen.getByText("Diseño 1")).toBeTruthy();
});

test("cancelling state disables the action and explains that the bars are frozen", () => {
  const state: ExecutionState = {
    lifecycle: ExecutionLifecycle.Cancelling,
    phase: ExecutionPhase.Generating,
    backend: BackendConnectionState.Connected,
    operationId: "operation-1",
    domainRunId: "domain-run-1",
    resuming: false,
    lastSequence: 2,
    needsReconciliation: false,
    overallCompleted: "1",
    overallTotal: "9007199254740992",
    validCases: 0, designs: [], activeDurationMs: 0, activeStartedAt: null, lastCheckpointAt: null,
    activeCase: null,
    confirmedCases: 0,
    completedCases: 0,
    failedCases: 0,
    error: null,
    eventLog: [],
  };

  render(<ExecutionProgress state={state} cancellationDelayed onCancel={() => undefined} onResume={() => undefined} onHome={() => undefined} />);

  expect(screen.getByRole("button", { name: "Cancelando…" }).hasAttribute("disabled")).toBe(true);
  expect(screen.queryByText("Preparando las etapas CORE")).toBeNull();
  expect(screen.queryByRole("progressbar", { name: "Preparando las etapas CORE" })).toBeNull();
  expect(screen.getByText(/No se iniciarán casos nuevos/)).toBeTruthy();
  expect(screen.getByText(/estado durable/)).toBeTruthy();
});

test("cancelled detail never presents the last CORE case as active or indeterminate", () => {
  const state: ExecutionState = {
    lifecycle: ExecutionLifecycle.Cancelled,
    phase: ExecutionPhase.CoreCase,
    backend: BackendConnectionState.Connected,
    operationId: null,
    domainRunId: "domain-run-1",
    resuming: false,
    lastSequence: 0,
    needsReconciliation: false,
    overallCompleted: 2,
    overallTotal: 10,
    validCases: 1, designs: [], activeDurationMs: 0, activeStartedAt: null, lastCheckpointAt: null,
    activeCase: { ordinal: 1, description: "Último caso", coreRunId: "core-1", designId: null, stage: null, stageCompleted: 0, stageTotal: null },
    confirmedCases: 1,
    completedCases: 0,
    failedCases: 0,
    error: null,
    eventLog: [],
  };
  render(<ExecutionProgress state={state} cancellationDelayed={false} onCancel={() => undefined} onResume={() => new Promise<void>(() => undefined)} onHome={() => undefined} />);

  expect(screen.queryByText("Preparando las etapas CORE")).toBeNull();
  expect(screen.queryByText("activo")).toBeNull();
  expect(screen.getAllByText("Cancelada").length).toBeGreaterThan(0);
  expect(screen.getByText("Último caso CORE")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Reanudar" }));
  const resumeButton = screen.getByRole("button", { name: "Reanudando…" });
  expect(resumeButton.getAttribute("aria-busy")).toBe("true");
  expect((resumeButton as HTMLButtonElement).disabled).toBe(true);
  expect(resumeButton.querySelector(".ui-action-spinner")).not.toBeNull();
  expect(resumeButton.querySelector(".ui-action-icon")).toBeNull();
});
