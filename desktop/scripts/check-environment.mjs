import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptsRoot = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(scriptsRoot, "..");
const repositoryRoot = path.resolve(desktopRoot, "..");

export function checkEnvironment() {
  const [major, minor] = process.versions.node.split(".").map(Number);
  if (major !== 22 || minor < 13) {
    throw new Error(
      [
        `Node ${process.versions.node} no está soportado; la aplicación requiere Node >=22.13.0.`,
        "Con nvm-windows ejecute: nvm install 22.17.1; nvm use 22.17.1",
        "Después confirme: node --version; npm --version; where.exe node; where.exe npm",
      ].join("\n"),
    );
  }

  const npmCli =
    process.env.npm_execpath ??
    path.join(path.dirname(process.execPath), "node_modules", "npm", "bin", "npm-cli.js");
  if (!existsSync(npmCli)) {
    throw new Error(`npm no pertenece al Node activo o su instalación está incompleta: ${npmCli}`);
  }
  const npmResult = spawnSync(process.execPath, [npmCli, "--version"], {
    cwd: desktopRoot,
    encoding: "utf8",
    shell: false,
  });
  if (npmResult.error || npmResult.status !== 0) {
    const diagnostic = npmResult.stderr?.trim() || npmResult.error?.message || "sin diagnóstico";
    throw new Error(`npm no funciona con el Node activo: ${diagnostic}`);
  }
  const npmVersion = npmResult.stdout.trim();
  const npmMajor = Number(npmVersion.split(".")[0]);
  if (npmMajor !== 10) throw new Error(`npm ${npmVersion} no está soportado; se requiere npm 10.x.`);

  const python =
    process.env.TESIS_DESKTOP_PYTHON ??
    path.join(repositoryRoot, ".venv", "Scripts", "python.exe");
  const required = [
    ["Python del gateway", python],
    ["Electron Forge", path.join(desktopRoot, "node_modules", "@electron-forge", "cli")],
    ["Schema gateway", path.join(repositoryRoot, "desktop_schemas", "1.0.0", "gateway-message.schema.json")],
  ];
  for (const [label, target] of required) {
    if (!existsSync(target)) throw new Error(`${label} no está disponible: ${target}`);
  }

  const pythonResult = spawnSync(python, ["-m", "tesis_desktop_gateway.cli", "--help"], {
    cwd: repositoryRoot,
    encoding: "utf8",
    shell: false,
  });
  if (pythonResult.error || pythonResult.status !== 0) {
    const diagnostic =
      pythonResult.stderr?.trim() || pythonResult.error?.message || "sin diagnóstico";
    throw new Error(`El gateway Python no puede iniciarse: ${diagnostic}`);
  }

  console.log(`[desktop:doctor] Node ${process.versions.node}: OK (${process.execPath})`);
  console.log(`[desktop:doctor] npm ${npmVersion}: OK (${npmCli})`);
  console.log(`[desktop:doctor] Gateway Python: OK (${python})`);
}

if (process.argv[1] !== undefined && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    checkEnvironment();
  } catch (error) {
    console.error(`[desktop:doctor] ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}
