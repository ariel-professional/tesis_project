import { readFileSync } from "node:fs";
import path from "node:path";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type {
  DomainOperationEvent,
  DomainUiHost,
  SingleRowFacilityLayoutDraft,
  SingleRowFacilityLayoutDraftV2,
} from "@domain-ui-sdk";
import { SingleRowFacilityLayoutScreen } from "@srfl-ui/screen";
import { SingleRowFacilityLayoutScreen as SingleRowFacilityLayoutScreenV1 } from "../../../src/tesis_domain_extensions/domains/single_row_facility_layout/ui/v1/src/screen";
import { StudyInformationStep } from "@srfl-ui/components/wizard/StudyInformationStep";
import { createEmptyDraft } from "@srfl-ui/config/defaults";

afterEach(cleanup);

test("new study keeps an internal identifier and edits a durable description", () => {
  const draft = createEmptyDraft();
  let updated = draft;
  render(<StudyInformationStep draft={draft} onChange={(value) => { updated = value; }} />);
  expect(draft.study.id).toMatch(/^study-[0-9a-f-]{36}$/);
  expect(screen.queryByRole("textbox", { name: "Identificador" })).toBeNull();
  const description = screen.getByRole("textbox", { name: /Descripción/ });
  expect(description.tagName).toBe("TEXTAREA");
  fireEvent.change(description, { target: { value: "Evaluar el sector de internación" } });
  expect(updated.study.description).toBe("Evaluar el sector de internación");
  expect(updated.study.id).toBe(draft.study.id);
});

test("Screen uses only the injected host", async () => {
  Object.defineProperty(window, "desktopApi", {
    configurable: true,
    get: () => {
      throw new Error("the domain UI accessed preload directly");
    },
  });
  const draft = JSON.parse(
    readFileSync(
      path.resolve(
        __dirname,
        "../../../examples/domains/single-row-facility-layout/v2-complete.json",
      ),
      "utf8",
    ),
  ) as SingleRowFacilityLayoutDraftV2;
  const host: DomainUiHost = {
    listTemplates: async () => [
      { template_id: "single-row-facility-layout/v1", domain_id: "single-row-facility-layout", domain_version: "1.0.0", name: "histórica" },
      { template_id: "single-row-facility-layout/v2-complete", domain_id: "single-row-facility-layout", domain_version: "2.0.0", name: "v2-complete" },
    ],
    openDefinitionFile: async () => null,
    loadTemplate: async <TDraft,>() => draft as TDraft,
    saveTemplate: async () => undefined,
    setRunTemplate: async () => undefined,
    validateStudy: async <TDraft,>(value: TDraft) => ({ valid: true, draft: value }),
    validateForest: async <TDraft,>(value: TDraft) => ({ valid: true, draft: value }),
    estimateCombinations: async () => ({ theoretical_combinations: 1 }),
    prepareStudy: async () => ({ domain_experiment_id: "a".repeat(64) }),
    startDomainRun: async () => ({
      operation_id: "11111111-1111-4111-8111-111111111111",
      domain_run_id: "22222222-2222-4222-8222-222222222222",
    }),
    cancelDomainRun: async () => undefined,
    resumeDomainRun: async () => ({
      operation_id: "33333333-3333-4333-8333-333333333333",
      domain_run_id: "22222222-2222-4222-8222-222222222222",
    }),
    listDomainRuns: async () => [],
    deleteDomainRun: async (domainRunId: string) => ({ deleted_domain_run_id: domainRunId, deleted_domain_experiment: null, preserved_template: false }),
    getDomainRun: async <TManifest,>() => ({}) as TManifest,
    subscribe: (_operationId: string, _observer: (event: DomainOperationEvent) => void) =>
      () => undefined,
    subscribeBackendState: () => () => undefined,
    getConfirmedResult: async <TResult,>() => ({}) as TResult,
    getResultMetrics: async <T,>() => ({}) as T,
  };

  render(<SingleRowFacilityLayoutScreen host={host} />);

  expect((await screen.findByRole("heading", { level: 1 })).textContent).toBe("Diseñá un experimento de adyacencias");
  expect(screen.getAllByText(/SRFL 2\.0\.0/).length).toBeGreaterThanOrEqual(2);
  expect(screen.queryByText("Histórica")).toBeNull();
  expect(screen.getAllByRole("button", { name: "Usar plantilla" })).toHaveLength(1);
  fireEvent.click(await screen.findByRole("button", { name: "Usar plantilla" }));
  expect((await screen.findAllByText(draft.study.title)).length).toBeGreaterThan(0);
});

test("the v1 application remains editable with its utility model", async () => {
  const draft = JSON.parse(
    readFileSync(
      path.resolve(
        __dirname,
        "../../../examples/domains/single-row-facility-layout/comparison.json",
      ),
      "utf8",
    ),
  ) as SingleRowFacilityLayoutDraft;
  const host: DomainUiHost = {
    listTemplates: async () => [{ template_id: "single-row-facility-layout/comparison", domain_id: "single-row-facility-layout", domain_version: "1.0.0", name: "comparison" }],
    openDefinitionFile: async () => null,
    loadTemplate: async <TDraft,>() => draft as TDraft,
    saveTemplate: async () => undefined,
    setRunTemplate: async () => undefined,
    validateStudy: async <TDraft,>(value: TDraft) => ({ valid: true, draft: value }),
    validateForest: async <TDraft,>(value: TDraft) => ({ valid: true, draft: value }),
    estimateCombinations: async () => ({ theoretical_combinations: 1 }),
    prepareStudy: async () => ({ domain_experiment_id: "b".repeat(64) }),
    startDomainRun: async () => ({ operation_id: "44444444-4444-4444-8444-444444444444", domain_run_id: "55555555-5555-4555-8555-555555555555" }),
    cancelDomainRun: async () => undefined,
    resumeDomainRun: async () => ({ operation_id: "66666666-6666-4666-8666-666666666666", domain_run_id: "55555555-5555-4555-8555-555555555555" }),
    listDomainRuns: async () => [],
    deleteDomainRun: async (domainRunId: string) => ({ deleted_domain_run_id: domainRunId, deleted_domain_experiment: null, preserved_template: false }),
    getDomainRun: async <TManifest,>() => ({}) as TManifest,
    subscribe: () => () => undefined,
    subscribeBackendState: () => () => undefined,
    getConfirmedResult: async <TResult,>() => ({}) as TResult,
    getResultMetrics: async <T,>() => ({}) as T,
  };

  render(<SingleRowFacilityLayoutScreenV1 host={host} />);
  expect((await screen.findAllByText(/SRFL 1\.0\.0/)).length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText("Plantilla · SRFL 1.0.0")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Usar plantilla" }));
  fireEvent.click(await screen.findByRole("button", { name: "Siguiente" }));
  fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(screen.getAllByLabelText(/Utilidad de/).length).toBeGreaterThan(0);
});
