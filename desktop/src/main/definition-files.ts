import { readFile } from "node:fs/promises";
import { dialog, type BrowserWindow } from "electron";

const MAX_DEFINITION_BYTES = 1024 * 1024;

export async function openDefinitionFile(window: BrowserWindow): Promise<unknown | null> {
  const selection = await dialog.showOpenDialog(window, {
    title: "Abrir definición de experimento",
    properties: ["openFile"],
    filters: [{ name: "Definición JSON", extensions: ["json"] }],
  });
  const selectedPath = selection.filePaths[0];
  if (selection.canceled || selectedPath === undefined) return null;
  const content = await readFile(selectedPath);
  if (content.byteLength > MAX_DEFINITION_BYTES) {
    throw new Error("La definición supera el máximo permitido de 1 MiB.");
  }
  try {
    return JSON.parse(content.toString("utf8")) as unknown;
  } catch {
    throw new Error("El archivo seleccionado no contiene JSON válido.");
  }
}

