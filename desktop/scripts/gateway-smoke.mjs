import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const scriptsRoot = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(scriptsRoot, "..");
const repositoryRoot = path.resolve(desktopRoot, "..");
const python =
  process.env.TESIS_DESKTOP_PYTHON ??
  path.join(repositoryRoot, ".venv", "Scripts", "python.exe");
const workspace = mkdtempSync(path.join(tmpdir(), "tesis-desktop-gateway-"));
mkdirSync(path.join(workspace, "experiments"));
mkdirSync(path.join(workspace, "runs"));

const gateway = spawn(
  python,
  [
    "-m",
    "tesis_desktop_gateway.cli",
    "--workspace",
    workspace,
    "--template-root",
    path.join(repositoryRoot, "examples"),
  ],
  { cwd: repositoryRoot, shell: false, windowsHide: true, stdio: ["pipe", "pipe", "pipe"] },
);
const lines = createInterface({ input: gateway.stdout });
const pending = new Map();
let diagnostics = "";
gateway.stderr.on("data", (chunk) => {
  diagnostics += chunk.toString("utf8");
});
lines.on("line", (line) => {
  try {
    const message = JSON.parse(line);
    const waiter = pending.get(message.request_id);
    if (waiter !== undefined) {
      pending.delete(message.request_id);
      waiter.resolve(message);
    }
  } catch (error) {
    for (const waiter of pending.values()) waiter.reject(error);
    pending.clear();
  }
});
const exited = new Promise((resolve) => gateway.once("exit", (code) => resolve(code)));

function request(command) {
  const requestId = randomUUID();
  const response = new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(requestId);
      reject(new Error(`Timeout esperando la respuesta de ${command}.`));
    }, 5000);
    pending.set(requestId, {
      resolve: (message) => {
        clearTimeout(timer);
        resolve(message);
      },
      reject: (error) => {
        clearTimeout(timer);
        reject(error);
      },
    });
  });
  gateway.stdin.write(
    `${JSON.stringify({
      protocol_version: "1.5",
      message_type: "request",
      request_id: requestId,
      command,
      params: {},
    })}\n`,
  );
  return response;
}

function assertSuccess(command, response) {
  if (
    response.protocol_version !== "1.5" ||
    response.message_type !== "response" ||
    response.status === "error"
  ) {
    throw new Error(`${command} devolvió una respuesta inválida: ${JSON.stringify(response)}`);
  }
}

try {
  assertSuccess("hello", await request("hello"));
  assertSuccess("ping", await request("ping"));
  assertSuccess("shutdown", await request("shutdown"));
  const exitCode = await Promise.race([
    exited,
    new Promise((_, reject) => setTimeout(() => reject(new Error("El gateway no terminó.")), 5000)),
  ]);
  if (exitCode !== 0) throw new Error(`El gateway terminó con ${exitCode}: ${diagnostics.trim()}`);
  console.log("[desktop:gateway-smoke] hello, ping y shutdown: OK");
} finally {
  lines.close();
  if (gateway.exitCode === null) gateway.kill();
  rmSync(workspace, { recursive: true, force: true });
}
