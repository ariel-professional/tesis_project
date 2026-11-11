import { createHash } from "node:crypto";
import { expect, test } from "vitest";
import {
  assertConfirmedDomainResult,
  resolveTransportedDomainResult,
} from "./gateway-result-transport";

function encode(bytes: Uint8Array): string {
  let binary = "";
  for (const value of bytes) binary += String.fromCharCode(value);
  return btoa(binary);
}

test("resolves a transported result before it reaches the domain UI", async () => {
  const document = {
    execution: {
      domain_run_id: "02d8098e-7a35-4172-8b8e-becc083a3acb",
      domain_experiment_id: "c0bbd1156ecbb290545e2d3760c38cc1b26774cd093e33182b4af777799ca477",
    },
    designs: [{ cases: Array.from({ length: 399 }, (_, index) => index) }],
  };
  const payload = new TextEncoder().encode(JSON.stringify(document));
  const digest = createHash("sha256").update(payload).digest("hex");

  const result = await resolveTransportedDomainResult(
    {
      $desktop_transport: "domain-result-file-v1",
      domain_run_id: document.execution.domain_run_id,
      size_bytes: payload.byteLength,
      sha256: digest,
    },
    async (_sha256, offset, length) => encode(payload.subarray(offset, offset + length)),
  );

  expect(() => assertConfirmedDomainResult(result)).not.toThrow();
  expect((result as typeof document).designs[0]?.cases).toHaveLength(399);
});

test("rejects a raw transport reference instead of crashing the React screen", () => {
  expect(() => assertConfirmedDomainResult({
    $desktop_transport: "domain-result-file-v1",
  })).toThrow("no contiene su referencia de ejecución");
});
