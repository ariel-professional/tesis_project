import { ActionButton, Button, Card, MetricCard, SwitchField } from "@domain-ui-kit";
import type { SrflEditorDraft } from "../../model/editor-draft.types";

type ReviewStepProps = {
  draft: SrflEditorDraft;
  estimate: number | string | null;
  validated: boolean;
  busy: boolean;
  error: string | null;
  template: boolean;
  onTemplateChange: (value: boolean) => void;
  onExecute: () => void;
};

export function ReviewStep({
  draft,
  estimate,
  validated,
  busy,
  error,
  template,
  onTemplateChange,
  onExecute,
}: ReviewStepProps) {
  const relLevels = [
    ...new Set(
      draft.decisionModel.relCloseness
        ?.filter((item) => ["A", "E", "I", "O"].includes(item.level))
        .map((item) => item.level) ?? [],
    ),
  ].sort();
  const candidatePairs = new Set(
    draft.study.components.flatMap((component) =>
      component.stationIds
        .slice(0, -1)
        .map((stationId, index) =>
          [stationId, component.stationIds[index + 1]!].sort().join("\0"),
        ),
    ),
  );
  const dimensions = [
    ...(draft.decisionModel.retainedCompatibleLayouts
      ? [{
          id: "retained-layouts",
          name: "Flexibilidad de distribución",
          detail: "Proporción exacta de disposiciones que siguen siendo posibles.",
          direction: "↑ Maximizar",
        }]
      : []),
    ...relLevels.map((level) => ({
      id: `rel-${level}`,
      name: `Cobertura de prioridades de cercanía · nivel ${level}`,
      detail: "Relaciones prioritarias que quedan garantizadas por las restricciones.",
      direction: "↑ Maximizar",
    })),
    ...draft.decisionModel.adjacencyMatrices.map((matrix) => ({
      id: `matrix-${matrix.id}`,
      name: matrix.name,
      detail: matrix.description,
      direction: matrix.direction === "maximize" ? "↑ Maximizar" : "↓ Minimizar",
    })),
  ];

  return (
    <section className="srfl-step srfl-review">
      <div className="srfl-step__intro">
        <h2>Revisión</h2>
        <p>Confirmá el alcance, los criterios y las fuentes antes de preparar el experimento.</p>
      </div>

      <div className="srfl-metrics" aria-label="Magnitudes del experimento">
        <MetricCard label="Estaciones" value={draft.study.stations.length} />
        <MetricCard label="Restricciones" value={draft.study.components.length} />
        <MetricCard label="Diseños" value={draft.study.designs.length} />
        <MetricCard label="Combinaciones teóricas" value={busy ? "Calculando…" : estimate ?? "—"} />
      </div>

      <div className="srfl-review-grid">
        <Card className="srfl-review-card">
          <header><span className="srfl-review-kicker">Estudio</span><h3>{draft.study.title || "Experimento sin título"}</h3></header>
          <p>{draft.study.description || "Sin descripción adicional."}</p>
          <dl className="srfl-review-facts">
            <div><dt>Estaciones</dt><dd>{draft.study.stations.length}</dd></div>
            <div><dt>Restricciones</dt><dd>{draft.study.components.length}</dd></div>
            <div><dt>Alternativas de diseño</dt><dd>{draft.study.designs.length}</dd></div>
          </dl>
        </Card>

        <Card className="srfl-review-card">
          <header><span className="srfl-review-kicker">Datos cualitativos</span><h3>Matriz REL</h3></header>
          {draft.decisionModel.relCloseness === null ? (
            <p>No se incluyó la matriz REL en este experimento.</p>
          ) : (
            <dl className="srfl-review-facts">
              <div><dt>Pares cargados</dt><dd>{draft.decisionModel.relCloseness.length}</dd></div>
              <div><dt>Niveles comparados</dt><dd>{relLevels.join(", ") || "Ninguno"}</dd></div>
              <div><dt>Políticas para relaciones X</dt><dd>{draft.decisionModel.undesiredPrescribedAdjacencies.length}</dd></div>
            </dl>
          )}
        </Card>
      </div>

      <section className="srfl-review-section" aria-labelledby="review-dimensions">
        <header>
          <div><h3 id="review-dimensions">Criterios de comparación</h3><p>Cada criterio participa como una dimensión independiente del análisis Pareto.</p></div>
          <span className="srfl-review-count">{dimensions.length}</span>
        </header>
        <div className="srfl-review-dimensions">
          {dimensions.map((dimension) => (
            <article key={dimension.id}>
              <div><strong>{dimension.name}</strong><span>{dimension.direction}</span></div>
              <p>{dimension.detail}</p>
            </article>
          ))}
        </div>
        <p className="srfl-review-policy">Si un caso factible no tiene un resultado concluyente en alguno de estos criterios, la clasificación Pareto del diseño se informará como inconclusa.</p>
      </section>

      {draft.decisionModel.adjacencyMatrices.length > 0 && (
        <section className="srfl-review-section" aria-labelledby="review-matrices">
          <header>
            <div><h3 id="review-matrices">Matrices cuantitativas</h3><p>Verificá objetivo, cobertura y fuente de cada matriz.</p></div>
            <span className="srfl-review-count">{draft.decisionModel.adjacencyMatrices.length}</span>
          </header>
          <div className="srfl-review-matrices">
            {draft.decisionModel.adjacencyMatrices.map((matrix) => {
              const covered = new Set(
                matrix.entries
                  .filter((entry) => Number(entry.value) > 0 && candidatePairs.has([entry.fromStationId, entry.toStationId].sort().join("\0")))
                  .map((entry) => [entry.fromStationId, entry.toStationId].sort().join("\0")),
              ).size;
              return (
                <Card key={matrix.id} className="srfl-review-matrix">
                  <header><h4>{matrix.name}</h4><span>{matrix.direction === "maximize" ? "↑ Maximizar" : "↓ Minimizar"}</span></header>
                  <p>{matrix.description}</p>
                  <dl className="srfl-review-facts">
                    <div><dt>Tipo</dt><dd>{matrix.directed ? "Dirigida" : "No dirigida"}</dd></div>
                    <div><dt>Unidad</dt><dd>{matrix.unit}</dd></div>
                    <div><dt>Período</dt><dd>{matrix.referencePeriod || "No especificado"}</dd></div>
                    <div><dt>Celdas completas</dt><dd>{matrix.entries.length}</dd></div>
                    <div><dt>Cobertura positiva</dt><dd>{covered}/{candidatePairs.size} restricciones</dd></div>
                    <div><dt>Fuente</dt><dd>{matrix.provenance}</dd></div>
                  </dl>
                </Card>
              );
            })}
          </div>
        </section>
      )}

      <Card className="srfl-review-execution">
        <div><span className="srfl-review-kicker">Ejecución</span><h3>Preparar el experimento</h3><p>La configuración será validada y fijada antes de iniciar el cálculo.</p></div>
        <SwitchField label="Guardar como plantilla" description="La definición quedará disponible para crear otros experimentos." checked={template} disabled={busy} onChange={onTemplateChange} />
        {error !== null && <p className="srfl-error" role="alert">{error}</p>}
        <ActionButton action="calculate" label={busy ? "Comprobando…" : "Preparar y ejecutar"} loading={busy} onClick={onExecute} disabled={!validated || busy} />
      </Card>
    </section>
  );
}
