import { ActionButton, ButtonVariant, Card } from "@domain-ui-kit";
import type { TemplateDescriptor } from "@domain-ui-sdk";
import { useState } from "react";

function templateLabel(name: string): string { return name.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
export function TemplateGallery({ templates, onSelect }: { templates: readonly TemplateDescriptor[]; onSelect: (template: TemplateDescriptor) => void | Promise<void> }) {
  const [opening, setOpening] = useState<string | null>(null);
  const open = async (template: TemplateDescriptor) => {
    if (opening !== null) return;
    setOpening(template.template_id);
    try { await onSelect(template); }
    finally { setOpening(null); }
  };
  return <div className="srfl-template-grid">{templates.map((template) => <Card key={template.template_id}><span className="ui-eyebrow">Plantilla · SRFL {template.domain_version}</span><h3>{templateLabel(template.name)}</h3><p>Usá esta definición como punto de partida y modificá cualquier sección.</p><ActionButton action="open" label={opening === template.template_id ? "Abriendo plantilla…" : "Usar plantilla"} loading={opening === template.template_id} disabled={opening !== null} variant={ButtonVariant.Secondary} onClick={() => void open(template)} /></Card>)}</div>;
}

