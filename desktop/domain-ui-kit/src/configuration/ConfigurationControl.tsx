import type { ConfigurationOptionDefinition } from "./configuration.types";
import { ConfigurationKind } from "./configuration.types";
import { NumberField, SelectField, SwitchField, TextField } from "../components/FormField";

export function ConfigurationControl<TDraft>({ definition, draft, onChange }: { definition: ConfigurationOptionDefinition<TDraft>; draft: TDraft; onChange: (draft: TDraft) => void }) {
  const common = { fieldName: definition.fieldName, label: definition.title, description: definition.description };
  switch (definition.kind) {
    case ConfigurationKind.Integer:
      return <NumberField {...common} min={definition.min} value={definition.getValue(draft)} onChange={(event) => onChange(definition.setValue(draft, Number(event.target.value)))} />;
    case ConfigurationKind.Boolean:
      return <SwitchField {...common} checked={definition.getValue(draft)} onChange={(value) => onChange(definition.setValue(draft, value))} />;
    case ConfigurationKind.Select:
      return <SelectField {...common} value={definition.getValue(draft)} options={definition.options} onChange={(event) => onChange(definition.setValue(draft, event.target.value))} />;
    case ConfigurationKind.Readonly:
      return <TextField {...common} value={definition.getValue(draft)} readOnly />;
  }
}

