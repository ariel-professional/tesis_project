import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { DomainRunDescriptor } from "@domain-ui-sdk";
import { Wizard } from "@domain-ui-kit";
import { RunsPage } from "@srfl-ui/components/home/RunsPage";
import { RunStatusChip } from "@srfl-ui/components/RunStatusChip";
import { ExecutionLifecycle } from "@srfl-ui/model/execution-state.types";

afterEach(cleanup);

test("run status chip presents every observable state in Spanish", () => {
  const states = [
    ["created", "Creada"],
    [ExecutionLifecycle.Running, "En curso"],
    [ExecutionLifecycle.Cancelling, "Cancelando"],
    [ExecutionLifecycle.Completed, "Completada"],
    [ExecutionLifecycle.Cancelled, "Cancelada"],
    [ExecutionLifecycle.Failed, "Fallida"],
    [ExecutionLifecycle.Interrupted, "Interrumpida"],
  ] as const;
  render(<>{states.map(([status]) => <RunStatusChip key={status} status={status} />)}</>);
  states.forEach(([, label]) => expect(screen.getByText(label)).toBeTruthy());
});

test("wizard prevents jumping beyond the highest enabled step", () => {
  render(<Wizard items={[{ id: "one", label: "Uno" }, { id: "two", label: "Dos" }]} current="one" highestEnabledIndex={0} onSelect={() => undefined} />);
  expect(screen.getByRole("button", { name: /Dos/ }).hasAttribute("disabled")).toBe(true);
});

test("run view action shows pending while durable data loads", async () => {
  let finish!: () => void;
  const loading = new Promise<void>((resolve) => { finish = resolve; });
  const run = { domain_run_id: "run-1", display_name: "Hospital central", status: "failed", updated_at: "2026-09-07T00:00:00Z", domain: { id: "single-row-facility-layout", version: "2.0.0" }, generation: { valid_selections: "23040", theoretical_combinations: "10461394944000" }, active_duration_ms: 7_500_000 } as DomainRunDescriptor;
  render(<RunsPage runs={[run]} onOpen={() => loading} onResume={async () => undefined} onDelete={async () => undefined} templateExperimentIds={[]} />);
  expect(screen.getByText("Fallida")).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Hospital central" })).toBeTruthy();
  expect(screen.getByTitle("run-1").textContent).toContain("run-1");
  expect(screen.getByText((_text, element) => element?.tagName === "P" && element.textContent?.includes("23.040") === true)).toBeTruthy();
  expect(screen.getByText((_text, element) => element?.tagName === "P" && element.textContent?.includes("10.461.394.944.000") === true)).toBeTruthy();
  expect(screen.queryByText("failed")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Ver detalles" }));
  const openingButton = await screen.findByRole("button", { name: "Abriendo…" });
  expect(openingButton.hasAttribute("disabled")).toBe(true);
  expect(openingButton.getAttribute("aria-busy")).toBe("true");
  expect(openingButton.querySelector(".ui-action-spinner")).not.toBeNull();
  expect(openingButton.querySelector(".ui-action-icon")).toBeNull();
  finish();
});

test("high-performance runs do not offer resume", () => {
  const run = { domain_run_id: "run-fast", display_name: "Rápida", status: "failed", updated_at: "2026-09-07T00:00:00Z", domain: { id: "single-row-facility-layout", version: "2.1.0" }, mode: "high_performance" } as DomainRunDescriptor;
  render(<RunsPage runs={[run]} onOpen={async () => undefined} onResume={async () => undefined} onDelete={async () => undefined} templateExperimentIds={[]} />);
  expect(screen.queryByRole("button", { name: "Reanudar" })).toBeNull();
});

test("run search matches accents and a hyphenless run UUID", () => {
  const run = {
    domain_run_id: "12345678-1234-4234-8234-123456789abc",
    domain_experiment_id: "a".repeat(64),
    display_name: "Disposición rápida",
    status: "completed",
    updated_at: "2026-09-07T00:00:00Z",
    domain: { id: "single-row-facility-layout", version: "2.0.0" },
  } as DomainRunDescriptor;
  render(<RunsPage runs={[run]} onOpen={async () => undefined} onResume={async () => undefined} onDelete={async () => undefined} templateExperimentIds={[]} />);

  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "disposicion RAPIDA" } });
  expect(screen.getByRole("heading", { name: "Disposición rápida" })).toBeTruthy();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "12345678123442348234123456789abc" } });
  expect(screen.getByRole("heading", { name: "Disposición rápida" })).toBeTruthy();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "a".repeat(64) } });
  expect(screen.getByRole("heading", { name: "Disposición rápida" })).toBeTruthy();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "missing" } });
  expect(screen.getByText("No hay coincidencias")).toBeTruthy();
});

test("delete confirmation cancellation does not call the host", async () => {
  const deleteRun = vi.fn(async () => undefined);
  const run = {
    domain_run_id: "12345678-1234-4234-8234-123456789abc",
    display_name: "Hospital central",
    status: "completed",
    updated_at: "2026-09-07T00:00:00Z",
    domain: { id: "single-row-facility-layout", version: "2.0.0" },
  } as DomainRunDescriptor;
  render(<RunsPage runs={[run]} onOpen={async () => undefined} onResume={async () => undefined} onDelete={deleteRun} templateExperimentIds={[]} />);

  fireEvent.click(screen.getByRole("button", { name: "Eliminar experimento" }));
  expect(screen.getByText(/Se perderán los resultados/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
  expect(deleteRun).not.toHaveBeenCalled();
});

test("delete confirmation calls the host only after explicit confirmation", async () => {
  const deleteRun = vi.fn(async () => undefined);
  const run = {
    domain_run_id: "12345678-1234-4234-8234-123456789abc",
    display_name: "Hospital central",
    status: "completed",
    updated_at: "2026-09-07T00:00:00Z",
    domain: { id: "single-row-facility-layout", version: "2.0.0" },
  } as DomainRunDescriptor;
  render(<RunsPage runs={[run]} onOpen={async () => undefined} onResume={async () => undefined} onDelete={deleteRun} templateExperimentIds={[]} />);

  fireEvent.click(screen.getByRole("button", { name: "Eliminar experimento" }));
  expect(deleteRun).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Eliminar ejecución y resultados" }));
  expect(deleteRun).toHaveBeenCalledWith(run.domain_run_id);
});
