import { mkdirSync } from "node:fs";
import path from "node:path";
import { app, BrowserWindow, ipcMain, shell } from "electron";
import started from "electron-squirrel-startup";
import { watchDevelopmentBackend } from "./development-watch";
import { openDefinitionFile } from "./definition-files";
import { GatewayClient } from "./gateway-client";
import { readDeleteDomainRunId, readDeleteDomainRunResult } from "./domain-run-delete";

declare const MAIN_WINDOW_WEBPACK_ENTRY: string;
declare const MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY: string;

if (started) app.quit();

let gateway: GatewayClient | null = null;
let stopDevelopmentWatch: (() => void) | null = null;
let quitting = false;
let gatewayRestart = Promise.resolve();
let deferredDevelopmentRestart = false;

type GatewayExitDetails = { code: number | null; interruptedOperationIds: readonly string[] };
type BackendState = "connected" | "restarting" | "disconnected";

const commands = {
  "desktop:attachments-begin": "attachments.begin",
  "desktop:attachments-append": "attachments.append",
  "desktop:attachments-finish": "attachments.finish",
  "desktop:attachments-abort": "attachments.abort",
  "desktop:attachments-read": "attachments.read",
  "desktop:study-documentation": "study.documentation",
  "desktop:domains-list": "domains.list",
  "desktop:decision-criteria": "layout.decision_criteria",
  "desktop:templates-list": "templates.list",
  "desktop:templates-load": "templates.load",
  "desktop:templates-save": "templates.save",
  "desktop:templates-set-for-run": "templates.set_for_run",
  "desktop:study-validate": "study.validate",
  "desktop:study-prepare": "study.prepare",
  "desktop:layout-validate-forest": "layout.validate_forest",
  "desktop:layout-estimate": "layout.estimate_combinations",
  "desktop:domain-run-start": "domain_run.start",
  "desktop:domain-run-cancel": "domain_run.cancel",
  "desktop:domain-run-resume": "domain_run.resume",
  "desktop:domain-run-status": "domain_run.status",
  "desktop:domain-run-list": "domain_run.list",
  "desktop:domain-run-delete": "domain_run.delete",
  "desktop:domain-run-result": "domain_run.result",
  "desktop:domain-run-case-page": "domain_run.case_page",
  "desktop:domain-run-case-detail": "domain_run.case_detail",
  "desktop:domain-run-dominators": "domain_run.dominators",
  "desktop:domain-run-frontier": "domain_run.frontier",
  "desktop:domain-run-plot-points": "domain_run.plot_points",
  "desktop:domain-run-plot-projection": "domain_run.plot_projection",
  "desktop:domain-run-metrics": "domain_run.metrics",
} as const;

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1240,
    height: 840,
    webPreferences: {
      preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  window.webContents.on("will-navigate", (event, targetUrl) => {
    if (targetUrl !== MAIN_WINDOW_WEBPACK_ENTRY) event.preventDefault();
  });
  window.webContents.on("did-fail-load", (_event, code, description, validatedUrl) => {
    console.error(`[desktop:renderer-load-error] ${code} ${description} (${validatedUrl})`);
  });
  window.webContents.on("console-message", (event) => {
    const details = event as typeof event & { level: string; message: string };
    const write = details.level === "error" ? console.error : console.log;
    write(`[desktop:renderer:${details.level}] ${details.message}`);
  });
  window.webContents.on("render-process-gone", (_event, details) => {
    console.error(`[desktop:renderer-gone] ${details.reason} (exit ${details.exitCode})`);
  });
  window.webContents.session.setPermissionRequestHandler((_webContents, _permission, callback) => {
    callback(false);
  });
  void window.loadURL(MAIN_WINDOW_WEBPACK_ENTRY).catch((error: unknown) => {
    console.error("[desktop:renderer-load-error] No se pudo cargar la ventana.", error);
  });
  return window;
}

async function confirmRendererReady(window: BrowserWindow): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    window.webContents.once("did-finish-load", () => resolve());
    window.webContents.once("did-fail-load", (_event, code, description) => {
      reject(new Error(`El renderer no cargó: ${code} ${description}`));
    });
  });
  const state = await window.webContents.executeJavaScript(`(async () => {
    const deadline = Date.now() + 10000;
    while (Date.now() < deadline) {
      const root = document.getElementById("root");
      const text = root?.textContent?.trim() ?? "";
      const alert = document.querySelector('[role="alert"]')?.textContent?.trim() ?? "";
      const hasDomainScreen = document.querySelector(".srfl-app") !== null;
      if (alert !== "" || hasDomainScreen) {
        return { childCount: root?.childElementCount ?? 0, text, alert, hasDomainScreen };
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    const root = document.getElementById("root");
    return {
      childCount: root?.childElementCount ?? 0,
      text: root?.textContent?.trim() ?? "",
      alert: "",
      hasDomainScreen: false,
    };
  })()`);
  if (state.alert !== "") {
    throw new Error(`El renderer mostró un error: ${state.alert}`);
  }
  if (state.childCount === 0 || state.text === "" || !state.hasDomainScreen) {
    throw new Error("React montó el shell, pero la pantalla del dominio no terminó de cargar.");
  }
  console.log(`[desktop:renderer-ready] Pantalla de dominio montada: ${state.text.slice(0, 160)}`);
}

async function launchGateway(workspace: string): Promise<GatewayClient> {
  const client = new GatewayClient(workspace);
  client.on("diagnostic", (message: string) => console.error(`[gateway] ${message.trimEnd()}`));
  await client.request("hello", {});
  return client;
}

function attachGateway(client: GatewayClient, window: BrowserWindow, workspace: string): void {
  client.on("event", (event: unknown) =>
    window.webContents.send("desktop:operation-event", event),
  );
  client.on("exit", (details: GatewayExitDetails) => {
    if (quitting || gateway !== client) return;
    gateway = null;
    sendBackendState(window, "disconnected", details.interruptedOperationIds);
    queueGatewayRestart(window, workspace, "unexpected-exit", details.interruptedOperationIds);
  });
}

function sendBackendState(
  window: BrowserWindow,
  state: BackendState,
  interruptedOperationIds: readonly string[] = [],
): void {
  if (window.isDestroyed()) return;
  window.webContents.send("desktop:backend-state", { state, interruptedOperationIds });
}

function queueGatewayRestart(
  window: BrowserWindow,
  workspace: string,
  reason: "development" | "unexpected-exit",
  interruptedOperationIds: readonly string[] = [],
): void {
  const current = gateway;
  if (reason === "development" && current?.isBusy) {
    if (!deferredDevelopmentRestart) {
      deferredDevelopmentRestart = true;
      console.log("[desktop:watch] El reinicio del gateway se difiere hasta terminar la operación activa.");
      current.once("idle", () => {
        deferredDevelopmentRestart = false;
        queueGatewayRestart(window, workspace, "development");
      });
    }
    return;
  }
  gatewayRestart = gatewayRestart.catch(() => undefined).then(async () => {
    if (quitting) return;
    const previous = gateway;
    sendBackendState(window, "restarting", interruptedOperationIds);
    if (previous !== null) {
      gateway = null;
      try {
        await previous.shutdown();
      } catch (error) {
        gateway = previous;
        sendBackendState(window, "connected", interruptedOperationIds);
        console.error("No se pudo cerrar el gateway anterior; se conserva la instancia activa.", error);
        return;
      }
    }
    if (quitting) return;
    try {
      const replacement = await launchGateway(workspace);
      gateway = replacement;
      attachGateway(replacement, window, workspace);
      sendBackendState(window, "connected", interruptedOperationIds);
      console.log("[desktop:ready] Gateway recargado y protocolo 1.5 confirmado.");
    } catch (error) {
      sendBackendState(window, "disconnected", interruptedOperationIds);
      console.error("No se pudo reiniciar el gateway.", error);
    }
  });
}

function registerIpcHandlers(window: BrowserWindow): void {
  ipcMain.handle("desktop:evidence-open-link", async (event, candidate: unknown) => {
    if (event.sender !== window.webContents || typeof candidate !== "string") throw new Error("Enlace no autorizado.");
    const url = new URL(candidate);
    if (!["http:", "https:"].includes(url.protocol) || !url.hostname) throw new Error("Usá un enlace HTTP o HTTPS.");
    await shell.openExternal(url.href);
  });
  ipcMain.handle("desktop:definition-open", async (ipcEvent) => {
    if (ipcEvent.sender !== window.webContents) throw new Error("Emisor IPC no autorizado.");
    return openDefinitionFile(window);
  });
  for (const [channel, command] of Object.entries(commands)) {
    ipcMain.handle(channel, async (ipcEvent, params: Record<string, unknown>) => {
      if (ipcEvent.sender !== window.webContents || gateway === null) {
        throw new Error("Emisor IPC no autorizado.");
      }
      const deletedRunId = command === "domain_run.delete" ? readDeleteDomainRunId(params) : null;
      const response = await gateway.request(command, params);
      if (command === "domain_run.delete") {
        readDeleteDomainRunResult(response.result, deletedRunId as string);
      }
      return {
        operation_id: response.operation_id,
        result: response.result,
      };
    });
  }
}

void app.whenReady().then(async () => {
  const workspace = path.join(app.getPath("userData"), "workspace");
  mkdirSync(path.join(workspace, "experiments"), { recursive: true });
  mkdirSync(path.join(workspace, "runs"), { recursive: true });
  const initialGateway = await launchGateway(workspace);
  const window = createWindow();
  gateway = initialGateway;
  attachGateway(initialGateway, window, workspace);
  registerIpcHandlers(window);
  await confirmRendererReady(window);
  console.log("[desktop:ready] Electron, renderer y gateway protocol 1.5 están listos.");

  if (!app.isPackaged) {
    const repositoryRoot = path.resolve(app.getAppPath(), "..");
    stopDevelopmentWatch = watchDevelopmentBackend(repositoryRoot, () => {
      console.log("[desktop:watch] Cambio Python detectado.");
      queueGatewayRestart(window, workspace, "development");
    });
  }

}).catch((error: unknown) => {
  console.error("No se pudo iniciar la aplicación desktop.", error);
  app.quit();
});

app.on("window-all-closed", () => app.quit());
app.on("before-quit", () => {
  quitting = true;
  stopDevelopmentWatch?.();
  stopDevelopmentWatch = null;
  if (gateway !== null) void gateway.shutdown().catch(() => undefined);
});
