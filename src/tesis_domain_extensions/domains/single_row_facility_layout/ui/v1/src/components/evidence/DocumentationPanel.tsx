import { EvidenceEditor } from "@domain-ui-kit";
import type { AttachmentService, SingleRowFacilityLayoutDraft } from "@domain-ui-sdk";
import { DocumentationSections } from "./DocumentationSections";

export function DocumentationPanel({ config, service, componentIds, designId }: {
  config: SingleRowFacilityLayoutDraft; service?: AttachmentService; componentIds?: readonly string[]; designId?: string;
}) {
  const entry = (key: string, title: string, value: Pick<typeof config.study, "description" | "attachments">) => ({
    key, title, content: <EvidenceEditor readOnly service={service} value={{ description: value.description ?? "", attachments: value.attachments ?? [] }} />,
  });
  return <details className="srfl-evidence-details"><summary>Antecedentes de las decisiones</summary>
    <DocumentationSections
      study={entry("study", config.study.title, config.study)}
      designs={config.study.designs.filter((item) => !designId || item.id === designId).map((item) => entry(item.id, item.title, item))}
      restrictions={config.study.components.filter((item) => !componentIds || componentIds.includes(item.id)).map((item) => entry(item.id, `${item.station_ids.join(" → ")} · ${item.id}`, item))}
    />
  </details>;
}
