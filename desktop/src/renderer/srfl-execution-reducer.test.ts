import {
  BackendConnectionState,
  type DomainOperationEvent,
  type SingleRowFacilityLayoutDomainRun,
} from "@domain-ui-sdk";
import { expect, test } from "vitest";
import { executionReducer, INITIAL_EXECUTION_STATE } from "@srfl-ui/model/execution-reducer";
import { ExecutionActionKind, ExecutionLifecycle } from "@srfl-ui/model/execution-state.types";

const operationId = "11111111-1111-4111-8111-111111111111";
const domainRunId = "22222222-2222-4222-8222-222222222222";

function event(value: Omit<DomainOperationEvent, "operation_id" | "protocol_version" | "message_type">): DomainOperationEvent {
  return { ...value, operation_id: operationId, protocol_version: "1.0", message_type: "event" } as DomainOperationEvent;
}

test("execution reducer freezes progress while cancelling and accepts the terminal", () => {
  let state = executionReducer(INITIAL_EXECUTION_STATE, {
    type: ExecutionActionKind.Accepted,
    operationId,
    domainRunId,
    resuming: false,
  });
  state = executionReducer(state, { type: ExecutionActionKind.EventReceived, event: event({
    event: "generation_started", sequence: 1, data: { domain_run_id: domainRunId, total: 100 },
  }) });
  state = executionReducer(state, { type: ExecutionActionKind.EventReceived, event: event({
    event: "generation_progress", sequence: 2, data: { domain_run_id: domainRunId, completed: 10, total: 100 },
  }) });
  state = executionReducer(state, { type: ExecutionActionKind.CancellationRequested });
  state = executionReducer(state, { type: ExecutionActionKind.EventReceived, event: event({
    event: "generation_progress", sequence: 3, data: { domain_run_id: domainRunId, completed: 20, total: 100 },
  }) });

  expect(state.lifecycle).toBe(ExecutionLifecycle.Cancelling);
  expect(state.overallCompleted).toBe(10);
  expect(state.lastSequence).toBe(3);

  state = executionReducer(state, { type: ExecutionActionKind.EventReceived, event: event({
    event: "terminal", sequence: 4, data: { domain_run_id: domainRunId, status: "cancelled" },
  }) });
  expect(state.lifecycle).toBe(ExecutionLifecycle.Cancelled);
});

test("execution reducer detects sequence gaps and backend interruption", () => {
  let state = executionReducer(INITIAL_EXECUTION_STATE, {
    type: ExecutionActionKind.Accepted,
    operationId,
    domainRunId,
    resuming: true,
  });
  state = executionReducer(state, { type: ExecutionActionKind.EventReceived, event: event({
    event: "generation_started", sequence: 1, data: { domain_run_id: domainRunId, total: "9007199254740992" },
  }) });
  state = executionReducer(state, { type: ExecutionActionKind.EventReceived, event: event({
    event: "generation_progress", sequence: 3, data: { domain_run_id: domainRunId, completed: "1", total: "9007199254740992" },
  }) });
  expect(state.needsReconciliation).toBe(true);

  state = executionReducer(state, {
    type: ExecutionActionKind.BackendChanged,
    state: BackendConnectionState.Disconnected,
    interruptedOperationIds: [operationId],
  });
  expect(state.lifecycle).toBe(ExecutionLifecycle.Interrupted);
});

test("starting a CORE case does not count it as completed before durable reconciliation", () => {
  let state = executionReducer(INITIAL_EXECUTION_STATE, {
    type: ExecutionActionKind.Accepted,
    operationId,
    domainRunId,
    resuming: false,
  });
  state = executionReducer(state, { type: ExecutionActionKind.EventReceived, event: event({
    event: "core_case_started",
    sequence: 1,
    data: { domain_run_id: domainRunId, ordinal: 1, description: "Caso", core_run_id: "core-1" },
  }) });

  expect(state.confirmedCases).toBe(1);
  expect(state.completedCases).toBe(0);
  expect(state.failedCases).toBe(0);
});

test("durable reconciliation separates completed and failed CORE cases", () => {
  const manifest: SingleRowFacilityLayoutDomainRun = {
    schema_version: "1.0.0",
    domain_run_id: domainRunId,
    domain_experiment_id: "experiment-1",
    domain: { id: "single-row-facility-layout", version: "1.0.0" },
    display_name: "Prueba",
    status: "failed",
    generator_cursor: 2,
    generation: {
      theoretical_combinations: 4,
      cycle_pruned_branches: 0,
      degree_pruned_branches: 0,
      valid_selections: 2,
      invalid_combinations: 0,
      duplicate_forests: 0,
      core_cases: 2,
    },
    cases: [
      {
        forest_id: "forest-1",
        core_experiment_id: "core-experiment-1",
        attempts: [{ core_run_id: "core-1", status: "completed" }],
        origins: [{ design_id: "d1", added_component_ids: [] }],
        payload: { component_ids: [], edges: [] },
      },
      {
        forest_id: "forest-2",
        core_experiment_id: "core-experiment-2",
        attempts: [{ core_run_id: "core-2", status: "failed" }],
        origins: [{ design_id: "d1", added_component_ids: ["c1"] }],
        payload: { component_ids: ["c1"], edges: [] },
      },
    ],
    created_at: "2026-09-03T00:00:00.000Z",
    updated_at: "2026-09-03T00:00:01.000Z",
  };
  let state = executionReducer(INITIAL_EXECUTION_STATE, {
    type: ExecutionActionKind.Accepted,
    operationId,
    domainRunId,
    resuming: false,
  });
  state = executionReducer(state, {
    type: ExecutionActionKind.Reconciled,
    manifest,
  });

  expect(state.confirmedCases).toBe(2);
  expect(state.completedCases).toBe(1);
  expect(state.failedCases).toBe(1);
  expect(state.lifecycle).toBe(ExecutionLifecycle.Failed);
  expect(state.activeCase?.description).toBe("Diseño en evaluación · 1 restricción agregada");
});

test("deduplicated CORE case keeps its first design as owner", () => {
  const manifest: SingleRowFacilityLayoutDomainRun = {
    schema_version: "2.0.0", domain_run_id: domainRunId, domain_experiment_id: "experiment-1",
    domain: { id: "single-row-facility-layout", version: "2.0.0" }, display_name: "Prueba", status: "cancelled",
    generator_cursor: 2,
    generation: { theoretical_combinations: 4, cycle_pruned_branches: 0, degree_pruned_branches: 0, valid_selections: 2, invalid_combinations: 0, structural_invalid_combinations: 0, forbidden_combinations: 0, duplicate_forests: 1, core_cases: 1 },
    designs: [{ design_id: "d1", design_title: "Primero", theoretical_combinations: 2 }, { design_id: "d2", design_title: "Segundo", theoretical_combinations: 2 }],
    cases: [{ forest_id: "forest-1", core_experiment_id: "core-1", attempts: [{ core_run_id: "core-1", status: "cancelled" }], origins: [{ design_id: "d1", added_component_ids: [] }, { design_id: "d2", added_component_ids: [] }], payload: { component_ids: [], edges: [] } }],
    active_duration_ms: 1500, active_started_at: null,
    created_at: "2026-09-03T00:00:00.000Z", updated_at: "2026-09-03T00:00:01.500Z",
  };
  const state = executionReducer(INITIAL_EXECUTION_STATE, { type: ExecutionActionKind.Reconciled, manifest });
  expect(state.activeCase?.designId).toBe("d1");
  expect(state.designs.map((design) => design.ownedCases)).toEqual([1, 0]);
  expect(state.validCases).toBe(2);
  expect(state.activeDurationMs).toBe(1500);
});

test("inspecting a non-terminal historical run does not resume it", () => {
  const manifest: SingleRowFacilityLayoutDomainRun = {
    schema_version: "1.0.0", domain_run_id: domainRunId, domain_experiment_id: "experiment-1",
    domain: { id: "single-row-facility-layout", version: "1.0.0" }, display_name: "Prueba", status: "running",
    generator_cursor: 0, generation: { theoretical_combinations: 1, cycle_pruned_branches: 0, degree_pruned_branches: 0, valid_selections: 0, invalid_combinations: 0, duplicate_forests: 0, core_cases: 0 },
    cases: [], created_at: "2026-09-03T00:00:00.000Z", updated_at: "2026-09-03T00:00:01.000Z",
  };
  const state = executionReducer(INITIAL_EXECUTION_STATE, { type: ExecutionActionKind.Inspected, manifest });
  expect(state.domainRunId).toBe(domainRunId);
  expect(state.operationId).toBeNull();
  expect(state.lifecycle).toBe(ExecutionLifecycle.Interrupted);
});
