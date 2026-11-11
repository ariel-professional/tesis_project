import type { ReactNode } from "react";
import type { ConfigurationSectionDefinition } from "./configuration.types";

export function ConfigurationSection<TDraft>({ definition, children }: { definition: ConfigurationSectionDefinition<TDraft>; children: ReactNode }) {
  return <section className="ui-configuration-section"><header><h3>{definition.title}</h3>{definition.description !== undefined && <p>{definition.description}</p>}</header><div className="ui-configuration-grid">{children}</div></section>;
}

