import { expect, test } from "vitest";
import { readDeleteDomainRunId, readDeleteDomainRunResult } from "./domain-run-delete";

const runId = "12345678-1234-4234-8234-123456789abc";

test("main validates the exact deletion request shape and canonical UUID", () => {
  expect(readDeleteDomainRunId({ domain_run_id: runId })).toBe(runId);
  expect(() => readDeleteDomainRunId({ domain_run_id: runId, extra: true })).toThrow();
  expect(() => readDeleteDomainRunId({ domain_run_id: runId.toUpperCase() })).toThrow();
  expect(() => readDeleteDomainRunId({ domain_run_id: "not-a-uuid" })).toThrow();
});

test("main validates the deletion response and requested run identity", () => {
  expect(readDeleteDomainRunResult({
    deleted_domain_run_id: runId,
    deleted_domain_experiment: "a".repeat(64),
    preserved_template: true,
  }, runId).preserved_template).toBe(true);
  expect(() => readDeleteDomainRunResult({
    deleted_domain_run_id: "87654321-4321-4321-8321-cba987654321",
    deleted_domain_experiment: null,
    preserved_template: false,
  }, runId)).toThrow();
});
