import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptsRoot = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(scriptsRoot, "..");

run("python", [path.resolve(desktopRoot, "../scripts/generate_desktop_registry.py")]);
run(process.execPath, [path.resolve(scriptsRoot, "generate-types.mjs")]);

function run(command, args) {
  const result = spawnSync(command, args, { cwd: desktopRoot, stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
