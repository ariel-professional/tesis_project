import type { DomainUiModule } from "@domain-ui-sdk";
import { useCallback, useEffect, useState } from "react";
import type { ElectronDomainUiHost } from "../host";
import { DomainLoader } from "./DomainLoader";
import { RendererErrorBoundary } from "./RendererErrorBoundary";
import { domainUiRegistry } from "../../generated/domain-registry";

type DomainDescriptor = {
  domain_id: string;
  domain_version: string;
  description: string;
};

export function DesktopShell({ host }: { host: ElectronDomainUiHost }) {
  const [identity, setIdentity] = useState("");
  const [available, setAvailable] = useState<DomainDescriptor[]>([]);
  const [module, setModule] = useState<DomainUiModule | null>(null);
  const [error, setError] = useState<string | null>(null);
  const acceptModule = useCallback(
    (loaded: DomainUiModule) => setModule(loaded),
    [],
  );

  useEffect(() => {
    void window.desktopApi
      .listDomains()
      .then(({ result }) => {
        const installed = (result as DomainDescriptor[]).filter((domain) =>
          Object.hasOwn(
            domainUiRegistry,
            `${domain.domain_id}@${domain.domain_version}`,
          ),
        );
        const first =
          installed.find(
            (domain) =>
              domain.domain_id === "single-row-facility-layout" &&
              domain.domain_version === "2.1.0",
          ) ?? installed[0];
        if (first === undefined)
          throw new Error("No hay dominios con UI disponibles.");
        setAvailable(installed);
        setIdentity(`${first.domain_id}@${first.domain_version}`);
      })
      .catch((reason: unknown) => setError(String(reason)));
  }, [host]);

  if (error !== null)
    return (
      <main className="shell-error" role="alert">
        {error}
      </main>
    );
  const changeIdentity = (nextIdentity: string) => {
    if (nextIdentity === identity) return;
    setModule(null);
    setIdentity(nextIdentity);
  };
  const Screen = module?.Screen;
  return (
    <div className="shell-domain">
      <header className="shell-version-selector">
        <label htmlFor="domain-version">Aplicación / modelo</label>
        <select
          id="domain-version"
          value={identity}
          disabled={identity === ""}
          onChange={(event) => changeIdentity(event.target.value)}
        >
          {available.map((domain) => {
            const value = `${domain.domain_id}@${domain.domain_version}`;
            return (
              <option key={value} value={value}>
                SRFL {domain.domain_version}
              </option>
            );
          })}
        </select>
      </header>
      <div className="shell-domain-content">
        {identity === "" ? (
          <main className="shell-loading" role="status">
            <span className="shell-loader" aria-hidden="true" />
            <p>Consultando aplicaciones instaladas…</p>
          </main>
        ) : Screen === undefined ? (
          <DomainLoader
            key={identity}
            identity={identity}
            onLoaded={acceptModule}
          />
        ) : (
          <RendererErrorBoundary key={identity}>
            <Screen host={host} />
          </RendererErrorBoundary>
        )}
      </div>
    </div>
  );
}
