import { randomUUID } from "node:crypto";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { EventEmitter } from "node:events";
import path from "node:path";
import { app } from "electron";
import Ajv from "ajv";
import gatewaySchema from "../../../desktop_schemas/1.5.0/gateway-message.schema.json";
import type { GatewayMessage, GatewayResponse } from "../generated/gateway-message";
import { gatewayExitMessage } from "./gateway-diagnostics";
import { resolveGatewayResult } from "./gateway-result-transport";

const MAX_MESSAGE_BYTES = 32 * 1024 * 1024;

export class GatewayClient extends EventEmitter {
  private readonly workspace: string;
  private readonly process: ChildProcessWithoutNullStreams;
  private readonly validateMessage: ReturnType<Ajv["compile"]>;
  private readonly pending = new Map<
    string,
    { resolve: (response: GatewayResponse) => void; reject: (error: Error) => void }
  >();
  private buffer = Buffer.alloc(0);
  private readonly activeOperations = new Set<string>();
  private protocolFailure: string | null = null;

  constructor(workspace: string) {
    super();
    this.workspace = workspace;
    const ajv = new Ajv({ allErrors: true, strict: false });
    this.validateMessage = ajv.compile(gatewaySchema);
    const repositoryRoot = app.isPackaged
      ? process.resourcesPath
      : path.resolve(app.getAppPath(), "..");
    const executable = process.env.TESIS_DESKTOP_PYTHON ?? (
      app.isPackaged
        ? path.join(process.resourcesPath, "python", "python.exe")
        : path.join(repositoryRoot, ".venv", "Scripts", "python.exe")
    );
    const templateRoot = app.isPackaged
      ? path.join(process.resourcesPath, "examples")
      : path.join(repositoryRoot, "examples");
    this.process = spawn(
      executable,
      [
        "-m",
        "tesis_desktop_gateway.cli",
        "--workspace",
        workspace,
        "--template-root",
        templateRoot,
      ],
      { cwd: repositoryRoot, shell: false, windowsHide: true, stdio: ["pipe", "pipe", "pipe"] },
    );
    this.process.stdout.on("data", (chunk: Buffer) => this.consume(chunk));
    this.process.stderr.on("data", (chunk: Buffer) => this.emit("diagnostic", chunk.toString("utf8")));
    this.process.once("exit", (code, signal) => {
      const error = new Error(gatewayExitMessage({ code, signal, protocolFailure: this.protocolFailure }));
      for (const pending of this.pending.values()) pending.reject(error);
      this.pending.clear();
      const interruptedOperationIds = [...this.activeOperations];
      this.activeOperations.clear();
      this.emit("exit", { code, interruptedOperationIds });
    });
  }

  get isBusy(): boolean {
    return this.activeOperations.size > 0;
  }

  get activeOperationIds(): readonly string[] {
    return [...this.activeOperations];
  }

  request(command: string, params: Record<string, unknown>): Promise<GatewayResponse> {
    if (this.process.exitCode !== null || this.process.stdin.destroyed) {
      return Promise.reject(new Error("El gateway no está disponible."));
    }
    const requestId = randomUUID();
    const request = {
      protocol_version: "1.5",
      message_type: "request",
      request_id: requestId,
      command,
      params,
    };
    if (!this.validateMessage(request)) {
      return Promise.reject(new Error(ajvMessage(this.validateMessage.errors)));
    }
    const payload = Buffer.from(`${JSON.stringify(request)}\n`, "utf8");
    if (payload.byteLength > MAX_MESSAGE_BYTES) {
      return Promise.reject(new Error("El mensaje excede el límite del gateway."));
    }
    return new Promise((resolve, reject) => {
      this.pending.set(requestId, { resolve, reject });
      this.process.stdin.write(payload, (error) => {
        if (error === null || error === undefined) return;
        if (this.pending.delete(requestId)) reject(error);
      });
    });
  }

  async shutdown(): Promise<void> {
    if (this.process.exitCode !== null) return;
    await this.request("shutdown", {});
  }

  private consume(chunk: Buffer): void {
    this.buffer = Buffer.concat([this.buffer, chunk]);
    if (this.buffer.byteLength > MAX_MESSAGE_BYTES) {
      this.terminateForProtocolFailure(`el frame superó ${MAX_MESSAGE_BYTES} bytes`);
      return;
    }
    for (;;) {
      const newline = this.buffer.indexOf(0x0a);
      if (newline < 0) return;
      const frame = this.buffer.subarray(0, newline);
      this.buffer = this.buffer.subarray(newline + 1);
      this.handleFrame(frame);
    }
  }

  private handleFrame(frame: Buffer): void {
    let message: GatewayMessage;
    try {
      message = JSON.parse(frame.toString("utf8")) as GatewayMessage;
    } catch {
      this.terminateForProtocolFailure("se recibió un frame que no es JSON válido");
      return;
    }
    if (!this.validateMessage(message)) {
      this.terminateForProtocolFailure(ajvMessage(this.validateMessage.errors));
      return;
    }
    if (message.message_type === "event") {
      if (message.event === "terminal") {
        this.activeOperations.delete(message.operation_id);
        if (!this.isBusy) this.emit("idle");
      }
      this.emit("event", message);
      return;
    }
    if (message.message_type !== "response") return;
    const pending = this.pending.get(message.request_id);
    if (pending === undefined) {
      this.terminateForProtocolFailure(`no existe una solicitud pendiente para ${message.request_id}`);
      return;
    }
    this.pending.delete(message.request_id);
    if (message.status === "error") {
      pending.reject(new Error(message.error?.message ?? "Error del gateway."));
    } else {
      if (message.status === "accepted" && message.operation_id !== null) {
        this.activeOperations.add(message.operation_id);
      }
      void this.resolveResponse(pending, message);
    }
  }

  private async resolveResponse(
    pending: { resolve: (response: GatewayResponse) => void; reject: (error: Error) => void },
    response: GatewayResponse,
  ): Promise<void> {
    try {
      const result = await resolveGatewayResult(this.workspace, response.result);
      pending.resolve({ ...response, result });
    } catch (error) {
      pending.reject(error instanceof Error ? error : new Error(String(error)));
    }
  }

  private terminateForProtocolFailure(reason: string): void {
    this.protocolFailure ??= reason;
    this.process.kill();
  }
}

function ajvMessage(errors: unknown): string {
  return `Mensaje desktop inválido: ${JSON.stringify(errors)}`;
}
