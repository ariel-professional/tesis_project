import {
  Button,
  ButtonVariant,
  Card,
  IconButton,
  Modal,
  Panel,
  SwitchField,
} from "@domain-ui-kit";
import type { DecisionCriterionDescriptor, DomainUiHost } from "@domain-ui-sdk";
import { useEffect, useState } from "react";
import type { SrflEditorDraft } from "../../model/editor-draft.types";

type Criterion = DecisionCriterionDescriptor;
const labels: Record<string, string> = {
  "core-layout-count": "cálculo automático",
  "rel-matrix": "matriz REL",
  "flow-matrix": "una o más matrices cuantitativas",
};

export function CriteriaStep({
  host,
  draft,
  onChange,
}: {
  host: DomainUiHost;
  draft: SrflEditorDraft;
  onChange: (draft: SrflEditorDraft) => void;
}) {
  const [catalog, setCatalog] = useState<readonly Criterion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [details, setDetails] = useState<Criterion | null>(null);
  const [pendingRemoval, setPendingRemoval] = useState<Criterion | null>(null);
  const retry = () => {
    setLoading(true);
    setError(null);
    const request = host.getLayoutDecisionCriteria;
    if (request === undefined) {
      setError("El host no ofrece el catálogo de criterios.");
      setLoading(false);
      return;
    }
    void request()
      .then((items) => setCatalog(items))
      .catch((reason: unknown) => setError(String(reason)))
      .finally(() => setLoading(false));
  };
  useEffect(retry, [host]);
  const setCriterion = (criterion: Criterion, checked: boolean, confirmed = false) => {
    const controlsFlow = criterion.required_inputs.includes("flow-matrix");
    if (!checked && controlsFlow && draft.decisionModel.adjacencyMatrices.length > 0 && !confirmed) {
      setPendingRemoval(criterion);
      return;
    }
    const selectedObjectives = checked
      ? [
          ...draft.decisionModel.selectedObjectives,
          { id: criterion.id, version: criterion.version },
        ]
      : draft.decisionModel.selectedObjectives.filter(
          (item) =>
            item.id !== criterion.id || item.version !== criterion.version,
        );
    const stations = draft.study.stations.map((item) => item.id).sort();
    const controlsRel = criterion.required_inputs.includes("rel-matrix");
    const needsRel = checked && controlsRel;
    const needsFlow = checked && controlsFlow;
    onChange({
      ...draft,
      decisionModel: {
        ...draft.decisionModel,
        selectedObjectives,
        retainedCompatibleLayouts: selectedObjectives.some(
          (item) => item.id === "retained-compatible-layouts",
        ),
        relCloseness:
          needsRel && draft.decisionModel.relCloseness === null
            ? stations.flatMap((first, index) =>
                stations
                  .slice(index + 1)
                  .map((second) => ({
                    firstStationId: first,
                    secondStationId: second,
                    level: "U" as const,
                    reason: "",
                    provenance: "",
                  })),
              )
            : !checked && controlsRel
              ? null
              : draft.decisionModel.relCloseness,
        adjacencyMatrices:
          needsFlow && draft.decisionModel.adjacencyMatrices.length === 0
            ? [{
                id: "matriz-1", name: "Matriz 1", description: "",
                direction: "maximize", unit: "", referencePeriod: "", provenance: "", directed: true,
                entries: stations.flatMap((from) => stations.filter((to) => to !== from).map((to) => ({ fromStationId: from, toStationId: to, value: "0" }))),
              }]
            : !checked && controlsFlow
              ? []
              : draft.decisionModel.adjacencyMatrices,
        undesiredPrescribedAdjacencies:
          !checked && controlsRel
            ? []
            : draft.decisionModel.undesiredPrescribedAdjacencies,
      },
    });
  };
  const selected = new Set(
    draft.decisionModel.selectedObjectives.map(
      (item) => `${item.id}@${item.version}`,
    ),
  );
  const matrices = new Set(
    catalog
      .filter((item) => selected.has(`${item.id}@${item.version}`))
      .flatMap((item) => item.required_inputs)
      .filter((input) => input !== "core-layout-count"),
  );
  if (loading)
    return (
      <section className="srfl-step" aria-busy="true">
        <p>Cargando catálogo de criterios…</p>
      </section>
    );
  if (error !== null)
    return (
      <section className="srfl-step" role="alert">
        <p>No se pudo cargar el catálogo: {error}</p>
        <Button variant={ButtonVariant.Secondary} onClick={retry}>
          Reintentar
        </Button>
      </section>
    );
  if (catalog.length === 0)
    return (
      <section className="srfl-step">
        <Panel>
          <h2>No hay criterios disponibles</h2>
          <p>El catálogo Python no devolvió criterios para este modelo.</p>
        </Panel>
      </section>
    );
  return (
    <section className="srfl-step">
      <div className="srfl-step__intro">
        <h2>Criterios de decisión</h2>
        <p>
          {selected.size} seleccionados ·{" "}
          {matrices.size
            ? `requieren ${[...matrices].map((item) => labels[item] ?? item).join(", ")}`
            : "sin carga adicional"}
          .
        </p>
      </div>
      <div className="srfl-criteria-grid">
        {catalog.map((criterion) => {
          const checked = selected.has(`${criterion.id}@${criterion.version}`);
          const unsupported = criterion.required_inputs.some(
            (input) => labels[input] === undefined,
          );
          return (
            <Card
              key={`${criterion.id}@${criterion.version}`}
              className={unsupported ? "is-disabled" : ""}
            >
              <div className="srfl-card-title">
                <div>
                  <h3>{criterion.name}</h3>
                  <p>{criterion.summary}</p>
                </div>
                <IconButton
                  label={`Información sobre ${criterion.name}`}
                  onClick={() => setDetails(criterion)}
                >
                  ⓘ
                </IconButton>
              </div>
              <div className="srfl-chips">
                <span>
                  {criterion.direction_mode === "per_instance"
                    ? "Objetivo configurable por matriz"
                    : criterion.direction === "maximize" ? "Maximizar" : "Minimizar"}
                </span>
                <span>{criterion.unit}</span>
                {criterion.required_inputs.map((input) => (
                  <span key={input}>
                    {labels[input] ?? `Insumo no soportado: ${input}`}
                  </span>
                ))}
              </div>
              <SwitchField
                label={
                  unsupported
                    ? "Insumo no soportado"
                    : checked
                      ? "Seleccionado"
                      : "Seleccionar criterio"
                }
                checked={checked}
                disabled={unsupported}
                onChange={(value) => setCriterion(criterion, value)}
              />
            </Card>
          );
        })}
      </div>
      {details !== null && (
        <Modal title={details.name} onClose={() => setDetails(null)}>
          <p>
            <strong>Pregunta de decisión:</strong> {details.decision_question}
          </p>
          <p>
            <strong>Cómo se calcula:</strong> {details.formula}
          </p>
          <p>
            <strong>Objetivo:</strong>{" "}
            {details.direction === "maximize"
              ? "Obtener el mayor valor"
              : "Obtener el menor valor"}{" "}
            · {details.unit}
          </p>
          <p>
            <strong>Datos necesarios:</strong>{" "}
            {details.required_inputs
              .map((item) => labels[item] ?? item)
              .join(", ")}
          </p>
        </Modal>
      )}
      {pendingRemoval !== null && (
        <Modal
          title="Quitar matrices cuantitativas"
          onClose={() => setPendingRemoval(null)}
          actions={<><Button variant={ButtonVariant.Secondary} onClick={() => setPendingRemoval(null)}>Conservar</Button><Button variant={ButtonVariant.Danger} onClick={() => { setCriterion(pendingRemoval, false, true); setPendingRemoval(null); }}>Quitar criterio y matrices</Button></>}
        >
          <p>Se eliminarán las {draft.decisionModel.adjacencyMatrices.length} matrices cargadas y todos sus valores.</p>
        </Modal>
      )}
    </section>
  );
}
