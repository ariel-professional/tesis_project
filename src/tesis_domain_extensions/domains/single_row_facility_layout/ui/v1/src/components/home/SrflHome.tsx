import { ButtonVariant, PageHeader } from "@domain-ui-kit";
import type { TemplateDescriptor } from "@domain-ui-sdk";
import { CreationOptionCard, HomeSection } from "./CreationOptionCard";
import { TemplateGallery } from "./TemplateGallery";

export function SrflHome({ templates, onNew, onTemplate, onOpenFile, onPaste }: { templates: readonly TemplateDescriptor[]; onNew: () => void; onTemplate: (template: TemplateDescriptor) => void | Promise<void>; onOpenFile: () => void; onPaste: () => void }) {
  return <main className="srfl-page"><PageHeader eyebrow="SRFL 1.0.0 · utilidad clásica" title="Diseñá un experimento de adyacencias" description="Definí estaciones, utilidades de restricciones y alternativas con el modelo original." />
    <div className="srfl-creation-grid">
      <CreationOptionCard icon="＋" title="Empezar desde cero" description="Construí un estudio nuevo paso a paso." action={onNew} actionLabel="Crear experimento" />
      <CreationOptionCard icon="↥" title="Abrir definición" description="Elegí un archivo JSON SRFL que ya tengas." action={onOpenFile} actionLabel="Seleccionar archivo" variant={ButtonVariant.Secondary} />
      <CreationOptionCard icon="⌘" title="Pegar definición" description="Importá una definición completa desde el portapapeles." action={onPaste} actionLabel="Pegar JSON" actionIcon="paste" variant={ButtonVariant.Secondary} />
    </div>
    <HomeSection title="Plantillas disponibles"><TemplateGallery templates={templates} onSelect={onTemplate} /></HomeSection>
  </main>;
}
