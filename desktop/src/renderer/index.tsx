import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { DesktopShell } from "./app/DesktopShell";
import { ElectronDomainUiHost } from "./host";
import "@domain-ui-kit";
import "./styles/shell.css";

const root = document.getElementById("root");
if (root === null) throw new Error("No se encontró el root del renderer.");
const host = new ElectronDomainUiHost();
window.addEventListener("beforeunload", () => host.dispose(), { once: true });
createRoot(root).render(<StrictMode><DesktopShell host={host} /></StrictMode>);
