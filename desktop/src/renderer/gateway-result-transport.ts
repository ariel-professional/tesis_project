const BLOCK_BYTES = 512 * 1024;
const DOMAIN_RESULT_TRANSPORT = "domain-result-file-v1";
const DOMAIN_RUN_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const SHA256 = /^[0-9a-f]{64}$/;

type DomainResultFileReference = {
  $desktop_transport: typeof DOMAIN_RESULT_TRANSPORT;
  domain_run_id: string;
  size_bytes: number;
  sha256: string;
};

type RangeReader = (sha256: string, offset: number, length: number) => Promise<string>;

export async function resolveTransportedDomainResult(
  result: unknown,
  readRange: RangeReader,
): Promise<unknown> {
  if (!isDomainResultFileReference(result)) return result;

  const payload = new Uint8Array(result.size_bytes);
  for (let offset = 0; offset < payload.length; offset += BLOCK_BYTES) {
    const expected = Math.min(BLOCK_BYTES, payload.length - offset);
    const encoded = await readRange(result.sha256, offset, expected);
    const binary = atob(encoded);
    if (binary.length !== expected) {
      throw new Error("La transferencia del resultado confirmado quedó incompleta.");
    }
    for (let index = 0; index < binary.length; index += 1) {
      payload[offset + index] = binary.charCodeAt(index);
    }
  }

  const buffer = payload.buffer.slice(payload.byteOffset, payload.byteOffset + payload.byteLength);
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  const hexadecimal = [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
  if (hexadecimal !== result.sha256) {
    throw new Error("La integridad del resultado confirmado no coincide con el gateway.");
  }
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(payload)) as unknown;
  } catch {
    throw new Error("El resultado confirmado no contiene JSON válido.");
  }
}

export function assertConfirmedDomainResult(
  value: unknown,
): asserts value is { execution: { domain_run_id: string; domain_experiment_id: string } } {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("El gateway devolvió un resultado de dominio inválido.");
  }
  const execution = (value as Record<string, unknown>).execution;
  if (typeof execution !== "object" || execution === null || Array.isArray(execution)) {
    throw new Error("El resultado confirmado no contiene su referencia de ejecución.");
  }
  const reference = execution as Record<string, unknown>;
  if (typeof reference.domain_run_id !== "string" || typeof reference.domain_experiment_id !== "string") {
    throw new Error("La referencia de ejecución del resultado confirmado es inválida.");
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
