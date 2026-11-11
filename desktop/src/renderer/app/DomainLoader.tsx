import type { DomainUiModule } from "@domain-ui-sdk";
import { useEffect, useState } from "react";
import { domainUiRegistry } from "../../generated/domain-registry";

export function DomainLoader({ identity, onLoaded }: { identity: string; onLoaded: (module: DomainUiModule) => void }) {
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setError(null);
    const load = domainUiRegistry[identity as keyof typeof domainUiRegistry];
    if (load === undefined) { setError(`No hay una interfaz instalada para ${identity}.`); return; }
    let active = true;
    void load().then((loaded) => { if (active) onLoaded(loaded); }).catch((reason: unknown) => { if (active) setError(String(reason)); });
    return () => { active = false; };
  }, [identity, onLoaded]);
  return error === null ? <main className="shell-loading" role="status"><span className="shell-loader" aria-hidden="true" /><p>Cargando {identity}…</p></main> : <main className="shell-error" role="alert">{error}</main>;
}
