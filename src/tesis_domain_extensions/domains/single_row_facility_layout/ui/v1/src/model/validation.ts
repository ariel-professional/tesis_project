import type { FieldError } from "@domain-ui-kit";
import { SrflEditorStep } from "./editor-state.types";
import type { SrflEditorDraft } from "./editor-draft.types";

export function validateStep(draft: SrflEditorDraft, step: SrflEditorStep): FieldError[] {
  const errors: FieldError[] = [];
  if (step === SrflEditorStep.Information && draft.study.title.trim() === "") errors.push({ field: "study.title", message: "Ingresá un título." });
  if (step === SrflEditorStep.Stations) {
    if (draft.study.stations.length === 0) errors.push({ field: "study.stations", message: "Agregá al menos una estación." });
    if (draft.study.stations.length > draft.execution.integer_limits.max_n) errors.push({ field: "study.stations", message: `El máximo configurado es ${draft.execution.integer_limits.max_n}.` });
    if (new Set(draft.study.stations.map((item) => item.id)).size !== draft.study.stations.length) errors.push({ field: "study.stations", message: "Los IDs de estación deben ser únicos." });
  }
  if (step === SrflEditorStep.Adjacencies) {
    if (draft.study.components.length === 0) errors.push({ field: "study.components", message: "Agregá al menos una restricción." });
    draft.study.components.forEach((item) => {
      if (item.stationIds.length < 2) errors.push({ field: item.clientKey, message: `${item.id} necesita al menos dos estaciones.` });
      if (new Set(item.stationIds).size !== item.stationIds.length) errors.push({ field: item.clientKey, message: `${item.id} repite estaciones.` });
    });
  }
  if (step === SrflEditorStep.Designs) {
    if (draft.study.designs.length === 0) errors.push({ field: "study.designs", message: "Agregá al menos un diseño." });
    draft.study.designs.forEach((item) => { if (item.baseComponentIds.length === 0) errors.push({ field: item.clientKey, message: `${item.title} debe incluir una restricción obligatoria.` }); });
  }
  return errors;
}

export function validateAll(draft: SrflEditorDraft): FieldError[] {
  return [SrflEditorStep.Information, SrflEditorStep.Stations, SrflEditorStep.Adjacencies, SrflEditorStep.Designs].flatMap((step) => validateStep(draft, step));
}
