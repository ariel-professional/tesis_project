import { watch, type FSWatcher } from "node:fs";
import path from "node:path";

export function watchDevelopmentBackend(
  repositoryRoot: string,
  onPythonChange: () => void,
): () => void {
  let debounce: NodeJS.Timeout | undefined;
  let watcher: FSWatcher;
  try {
    watcher = watch(path.join(repositoryRoot, "src"), { recursive: true }, (_event, filename) => {
      const relative = filename?.toString().replaceAll("\\", "/") ?? "";
      if (relative !== "" && (!relative.endsWith(".py") || relative.includes("/__pycache__/"))) {
        return;
      }
      clearTimeout(debounce);
      debounce = setTimeout(onPythonChange, 250);
    });
  } catch (error) {
    console.error("No se pudo observar el backend Python.", error);
    return () => undefined;
  }
  watcher.on("error", (error) => console.error("Falló el watch del backend Python.", error));
  return () => {
    clearTimeout(debounce);
    watcher.close();
  };
}
