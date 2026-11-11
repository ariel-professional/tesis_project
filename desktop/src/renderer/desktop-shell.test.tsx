import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { DesktopShell } from "./app/DesktopShell";
import type { ElectronDomainUiHost } from "./host";

vi.mock("./app/DomainLoader", () => ({ DomainLoader: ({ identity }: { identity: string }) => <p>{identity}</p> }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("startup selects v2.1 and the application selector can load the complete v1 module", async () => {
  const listDomains = vi.fn().mockResolvedValue({ result: [
    { domain_id: "inspection-route", domain_version: "1.0.0" },
    { domain_id: "single-row-facility-layout", domain_version: "1.0.0" },
    { domain_id: "single-row-facility-layout", domain_version: "2.0.0" },
    { domain_id: "single-row-facility-layout", domain_version: "2.1.0" },
  ] });
  vi.stubGlobal("desktopApi", { listDomains });
  render(<DesktopShell host={{} as ElectronDomainUiHost} />);
  await waitFor(() => expect(listDomains).toHaveBeenCalled());
  expect(await screen.findByText("single-row-facility-layout@2.1.0")).toBeTruthy();
  expect(screen.queryByText("inspection-route@1.0.0")).toBeNull();
  fireEvent.change(screen.getByLabelText("Aplicación / modelo"), { target: { value: "single-row-facility-layout@1.0.0" } });
  expect(screen.getByText("single-row-facility-layout@1.0.0")).toBeTruthy();
});
