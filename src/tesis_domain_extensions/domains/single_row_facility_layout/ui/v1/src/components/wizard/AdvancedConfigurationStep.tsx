import { ConfigurationOption, ConfigurationSection } from "@domain-ui-kit";
import { SRFL_CONFIGURATION_SECTIONS } from "../../config/advanced-options";
import type { SrflEditorDraft } from "../../model/editor-draft.types";

export function AdvancedConfigurationStep({ draft, onChange }: { draft: SrflEditorDraft; onChange: (draft: SrflEditorDraft) => void }) {
  return <section className="srfl-step"><div className="srfl-step__intro"><h2>Configuración avanzada</h2><p>Estos valores controlan límites y evidencia. El nombre técnico se muestra para que cada opción sea inequívoca.</p></div>{SRFL_CONFIGURATION_SECTIONS.map((section) => <ConfigurationSection key={section.id} definition={section}>{section.options.map((option) => <ConfigurationOption key={option.fieldName} definition={option} draft={draft} onChange={onChange} />)}</ConfigurationSection>)}</section>;
}

