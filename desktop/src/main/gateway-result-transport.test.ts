import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, expect, test } from "vitest";
import { resolveGatewayResult } from "./gateway-result-transport";

const temporaryRoots: string[] = [];

afterEach(() => {
  for (const root of temporaryRoots.splice(0)) rmSync(root, { recursive: true, force: true });
});

test("leaves ordinary inline gateway results unchanged", async () => {
  const inline = { cases: [1, 2, 3] };
  await expect(resolveGatewayResult("unused", inline)).resolves.toBe(inline);
});

test("loads and verifies a confirmed result larger than one gateway frame", async () => {
  const workspace = mkdtempSync(path.join(tmpdir(), "tesis-large-result-"));
  temporaryRoots.push(workspace);
  const domainRunId = "02d8098e-7a35-4172-8b8e-becc083a3acb";
  const directory = path.join(workspace, "domain_runs", domainRunId);
  mkdirSync(directory, { recursive: true });
  const payload = Buffer.from(JSON.stringify({ content: "x".repeat(17 * 1024 * 1024) }), "utf8");
  writeFileSync(path.join(directory, "result.json"), payload);

  const result = await resolveGatewayResult(workspace, {
    $desktop_transport: "domain-result-file-v1",
    domain_run_id: domainRunId,
    size_bytes: payload.byteLength,
    sha256: createHash("sha256").update(payload).digest("hex"),
  });

  expect((result as { content: string }).content).toHaveLength(17 * 1024 * 1024);
});
