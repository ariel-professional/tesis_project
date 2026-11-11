import { spawn, spawnSync } from "node:child_process";
import { watch } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { checkEnvironment } from "./check-environment.mjs";

const scriptsRoot = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(scriptsRoot, "..");
const repositoryRoot = path.resolve(desktopRoot, "..");
const generateScript = path.join(scriptsRoot, "generate-all.mjs");
const forgeCli = path.join(
  desktopRoot,
  "node_modules",
  "@electron-forge",
  "cli",
  "dist",
  "electron-forge.js",
);

function generate() {
  const result = spawnSync(process.execPath, [generateScript], {
    cwd: desktopRoot,
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`La generación desktop terminó con ${result.status}.`);
}

try {
  checkEnvironment();
} catch (error) {
  console.error(`[desktop:dev] ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
}
generate();

const childEnvironment = { ...process.env };
delete childEnvironment.ELECTRON_RUN_AS_NODE;
const forge = spawn(process.execPath, [forgeCli, "start"], {
  cwd: desktopRoot,
  env: childEnvironment,
  stdio: "inherit",
});

let generationTimer;
let generationRunning = false;
let generationQueued = false;
const watchers = [];

function scheduleGeneration(reason) {
  clearTimeout(generationTimer);
  generationTimer = setTimeout(() => runGeneration(reason), 200);
}

function runGeneration(reason) {
  if (generationRunning) {
    generationQueued = true;
    return;
  }
  generationRunning = true;
  console.log(`[desktop:watch] Regenerando por cambio en ${reason}.`);
  try {
    generate();
  } catch (error) {
    console.error(`[desktop:watch] ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    generationRunning = false;
    if (generationQueued) {
      generationQueued = false;
      scheduleGeneration("entradas acumuladas");
    }
  }
}

function addWatcher(root, accepts) {
  const watcher = watch(root, { recursive: true }, (_event, filename) => {
    const relative = filename?.toString().replaceAll("\\", "/") ?? "";
    if (accepts(relative)) scheduleGeneration(relative || root);
  });
  watcher.on("error", (error) => console.error(`[desktop:watch] ${error.message}`));
  watchers.push(watcher);
}

addWatcher(path.join(repositoryRoot, "src"), (file) =>
  file.includes("/ui/") && /^domain-ui(?:-[^/]+)?\.json$/.test(path.posix.basename(file)),
);
addWatcher(path.join(repositoryRoot, "desktop_schemas"), (file) => file.endsWith(".schema.json"));
addWatcher(
  path.join(repositoryRoot, "domain_schemas", "single-row-facility-layout"),
  (file) => file.endsWith(".schema.json"),
);
addWatcher(
  path.join(repositoryRoot, "scripts"),
  (file) => file === "generate_desktop_registry.py",
);
addWatcher(
  scriptsRoot,
  (file) => file === "generate-all.mjs" || file === "generate-types.mjs",
);

function closeWatchers() {
  clearTimeout(generationTimer);
  for (const watcher of watchers) watcher.close();
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    closeWatchers();
    if (!forge.killed) forge.kill(signal);
  });
}

forge.once("error", (error) => {
  closeWatchers();
  console.error(`[desktop:watch] No se pudo iniciar Electron Forge: ${error.message}`);
  process.exitCode = 1;
});

forge.once("exit", (code, signal) => {
  closeWatchers();
  if (signal === null) process.exitCode = code ?? 1;
});

console.log("[desktop:dev] Iniciando Electron; este comando queda activo hasta presionar Ctrl+C.");
console.log("[desktop:dev] Espere el mensaje [desktop:ready] antes de usar la ventana.");
