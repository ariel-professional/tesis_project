import { createHash } from "node:crypto";
import { lstat, readFile, realpath } from "node:fs/promises";
import path from "node:path";

const DOMAIN_RESULT_TRANSPORT = "domain-result-file-v1";
const DOMAIN_RUN_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const SHA256 = /^[0-9a-f]{64}$/;

type DomainResultFileReference = {
  $desktop_transport: typeof DOMAIN_RESULT_TRANSPORT;
  domain_run_id: string;
  size_bytes: number;
  sha256: string;
};

export async function resolveGatewayResult(workspace: string, result: unknown): Promise<unknown> {
  if (!isDomainResultFileReference(result)) return result;

  const workspaceRoot = await realpath(workspace);
  const candidate = path.join(workspaceRoot, "domain_runs", result.domain_run_id, "result.json");
  const metadata = await lstat(candidate);
  if (!metadata.isFile() || metadata.isSymbolicLink()) {
    throw new Error("El resultado confirmado no es un archivo regular.");
  }
  const resolved = await realpath(candidate);
  const relative = path.relative(workspaceRoot, resolved);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error("El resultado confirmado está fuera del workspace.");
  }

  const payload = await readFile(resolved);
  if (payload.byteLength !== result.size_bytes) {
    throw new Error("El tamaño del resultado confirmado no coincide con el anunciado.");
  }
  const digest = createHash("sha256").update(payload).digest("hex");
  if (digest !== result.sha256) {
    throw new Error("La integridad del resultado confirmado no coincide con el gateway.");
  }
  try {
    return JSON.parse(payload.toString("utf8")) as unknown;
  } catch {
    throw new Error("El resultado confirmado no contiene JSON válido.");
  }
}

function isDomainResultFileReference(value: unknown): value is DomainResultFileReference {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  return candidate.$desktop_transport === DOMAIN_RESULT_TRANSPORT
    && typeof candidate.domain_run_id === "string"
    && DOMAIN_RUN_ID.test(candidate.domain_run_id)
    && typeof candidate.size_bytes === "number"
    && Number.isSafeInteger(candidate.size_bytes)
    && candidate.size_bytes >= 0
    && typeof candidate.sha256 === "string"
    && SHA256.test(candidate.sha256);
}
