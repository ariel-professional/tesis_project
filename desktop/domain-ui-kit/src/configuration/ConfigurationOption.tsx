import type { ConfigurationOptionDefinition } from "./configuration.types";
import { ConfigurationControl } from "./ConfigurationControl";

export function ConfigurationOption<TDraft>(props: { definition: ConfigurationOptionDefinition<TDraft>; draft: TDraft; onChange: (draft: TDraft) => void }) {
  return <div className="ui-configuration-option"><ConfigurationControl {...props} /></div>;
}

