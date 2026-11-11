import type { FieldError } from "@domain-ui-kit";
import type { SrflEditorDraft } from "./editor-draft.types";
import { SrflEditorStep } from "./editor-state.types";
import { canonicalPairKey, directedPairKey } from "./matrix-pairs";

const isExactSet = (actual: string[], expected: Set<string>) => actual.length === expected.size && new Set(actual).size === actual.length && actual.every((item) => expected.has(item));
const componentPairKeys = (draft: SrflEditorDraft): Set<string> => new Set(draft.study.components.flatMap((component) => component.stationIds.slice(0, -1).map((stationId, index) => canonicalPairKey(stationId, component.stationIds[index + 1]!))));

export function validateStep(draft: SrflEditorDraft, step: SrflEditorStep): FieldError[] {
  const errors: FieldError[] = [];
  if (step === SrflEditorStep.Information && draft.study.title.trim() === "") errors.push({ field: "study.title", message: "Ingresá un título." });
  if (step === SrflEditorStep.Criteria && draft.decisionModel.selectedObjectives.length === 0) errors.push({ field: "decisionModel", message: "Seleccioná al menos un criterio de decisión." });
  if (step === SrflEditorStep.Relations) {
    const stationIds = draft.study.stations.map((item) => item.id);
    const expectedPairs = new Set(stationIds.flatMap((first, index) => stationIds.slice(index + 1).map((second) => canonicalPairKey(first, second))));
    if ((draft.decisionModel.relCloseness !== null || draft.decisionModel.adjacencyMatrices.length > 0) && draft.study.stations.length < 2) errors.push({ field: "study.stations", message: "Las matrices de relaciones requieren al menos dos estaciones." });
    if (draft.decisionModel.relCloseness !== null && !isExactSet(draft.decisionModel.relCloseness.map((item) => canonicalPairKey(item.firstStationId, item.secondStationId)), expectedPairs)) errors.push({ field: "decisionModel.relCloseness", message: "La matriz REL debe contener cada par de estaciones exactamente una vez." });
    draft.decisionModel.relCloseness?.forEach((item) => {
      if (item.reason.trim() === "") errors.push({ field: "decisionModel.relCloseness", message: `Indicá por qué se asignó el nivel a ${item.firstStationId} · ${item.secondStationId}.` });
      if (item.provenance.trim() === "") errors.push({ field: "decisionModel.relCloseness", message: `Indicá la fuente de los datos para ${item.firstStationId} · ${item.secondStationId}.` });
    });
    const matrixIds = draft.decisionModel.adjacencyMatrices.map((item) => item.id);
    const matrixNames = draft.decisionModel.adjacencyMatrices.map((item) => item.name.trim().toLocaleLowerCase());
    if (new Set(matrixIds).size !== matrixIds.length) errors.push({ field: "decisionModel.adjacencyMatrices", message: "Cada matriz debe tener un identificador único." });
    if (new Set(matrixNames).size !== matrixNames.length) errors.push({ field: "decisionModel.adjacencyMatrices", message: "Cada matriz debe tener un nombre único." });
    draft.decisionModel.adjacencyMatrices.forEach((matrix) => {
      const field = `decisionModel.adjacencyMatrices.${matrix.id}`;
      const expected = matrix.directed ? new Set(stationIds.flatMap((from) => stationIds.filter((to) => to !== from).map((to) => directedPairKey(from, to)))) : expectedPairs;
      const actual = matrix.entries.map((item) => matrix.directed ? directedPairKey(item.fromStationId, item.toStationId) : canonicalPairKey(item.fromStationId, item.toStationId));
      if (!isExactSet(actual, expected)) errors.push({ field, message: `${matrix.name || matrix.id}: la matriz debe contener cada celda requerida exactamente una vez.` });
      if ([matrix.id, matrix.name, matrix.description, matrix.provenance].some((value) => value.trim() === "")) errors.push({ field, message: `${matrix.name || matrix.id}: completá nombre, descripción y fuente de los datos.` });
      matrix.entries.forEach((item) => {
        if (item.value.trim() === "" || !/^-?\d+(?:\.\d+)?$/.test(item.value)) errors.push({ field, message: `El valor ${item.fromStationId} → ${item.toStationId} debe ser un decimal válido.` });
      });
    });
    const selected = draft.decisionModel.selectedObjectives.some((item) => item.id === "captured-adjacency-flow");
    if (selected && draft.decisionModel.adjacencyMatrices.length === 0) errors.push({ field: "decisionModel.adjacencyMatrices", message: "Agregá al menos una matriz cuantitativa." });
    if (!selected && draft.decisionModel.adjacencyMatrices.length > 0) errors.push({ field: "decisionModel.adjacencyMatrices", message: "Las matrices cuantitativas requieren seleccionar el criterio Valor de adyacencias." });
    if (draft.decisionModel.relCloseness !== null) {
      const xPairs = new Set(draft.decisionModel.relCloseness.filter((item) => item.level === "X").map((item) => canonicalPairKey(item.firstStationId, item.secondStationId)));
      const policies = draft.decisionModel.undesiredPrescribedAdjacencies;
      const policyPairs = policies.map((item) => canonicalPairKey(item.firstStationId, item.secondStationId));
      if (!isExactSet(policyPairs, xPairs)) errors.push({ field: "decisionModel.undesiredPrescribedAdjacencies", message: "Cada relación X debe tener exactamente una política explícita y sólo las relaciones X pueden tenerla." });
      policies.forEach((item) => { if (item.cause === "" || item.explanation.trim() === "" || item.provenance.trim() === "") errors.push({ field: "decisionModel.undesiredPrescribedAdjacencies", message: `Completá motivo, explicación y fuente para ${item.firstStationId} · ${item.secondStationId}.` }); });
    }
  }
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
    const availablePairs = componentPairKeys(draft);
    const selectedIds = new Set(draft.decisionModel.selectedObjectives.map((item) => item.id));
    if (selectedIds.has("rel-closeness") && draft.decisionModel.relCloseness !== null) {
      const priorityLevels = ["A", "E", "I", "O"] as const;
      const priorities = draft.decisionModel.relCloseness.filter((item) => priorityLevels.includes(item.level as typeof priorityLevels[number]));
      if (priorities.length === 0) errors.push({ field: "decisionModel.relCloseness", message: "El criterio REL necesita al menos una relación prioritaria A, E, I u O." });
      for (const level of priorityLevels) {
        const relations = draft.decisionModel.relCloseness.filter((item) => item.level === level);
        if (relations.length > 0 && !relations.some((item) => availablePairs.has(canonicalPairKey(item.firstStationId, item.secondStationId)))) errors.push({ field: "study.components", message: `El nivel REL ${level} no puede variar: convertí al menos una de sus relaciones en restricción candidata.` });
      }
    }
  }
  if (step === SrflEditorStep.Designs) {
    if (draft.study.designs.length === 0) errors.push({ field: "study.designs", message: "Agregá al menos un diseño." });
    if (draft.study.designs.filter((item) => item.baseComponentIds.length === 0).length > 1) errors.push({ field: "study.designs", message: "Sólo puede existir un diseño de control sin restricciones obligatorias." });
  }
  return errors;
}

export function validateAll(draft: SrflEditorDraft): FieldError[] {
  return [SrflEditorStep.Information, SrflEditorStep.Stations, SrflEditorStep.Criteria, SrflEditorStep.Relations, SrflEditorStep.Adjacencies, SrflEditorStep.Designs].flatMap((step) => validateStep(draft, step));
}
