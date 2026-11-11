import {
  Button,
  ButtonVariant,
  DependencyConfirmationModal,
  Panel,
} from "@domain-ui-kit";
import { useEffect, useMemo, useState } from "react";
import type {
  RelRequirementDraft,
  SrflEditorDraft,
} from "../../model/editor-draft.types";
import {
  nextClientKey,
  slugify,
  uniqueIdentifier,
} from "../../model/identifiers";
import { AdjacencyDiagram } from "../adjacencies/AdjacencyDiagram";
import { AdjacencyTable } from "../adjacencies/AdjacencyTable";

const pairKey = (first: string, second: string) =>
  [first, second].sort().join("\0");

function componentPairs(draft: SrflEditorDraft): Set<string> {
  return new Set(
    draft.study.components.flatMap((component) =>
      component.stationIds
        .slice(0, -1)
        .map((stationId, index) =>
          pairKey(stationId, component.stationIds[index + 1]!),
        ),
    ),
  );
}

function pairFlow(
  draft: SrflEditorDraft,
  first: string,
  second: string,
): number | null {
  const flow = draft.decisionModel.adjacencyMatrices[0];
  if (flow === undefined) return null;
  return flow.entries.reduce((total, entry) => {
    const forward =
      entry.fromStationId === first && entry.toStationId === second;
    const reverse =
      entry.fromStationId === second && entry.toStationId === first;
    return forward || reverse ? total + Number(entry.value || 0) : total;
  }, 0);
}

function relationFor(
  draft: SrflEditorDraft,
  first: string,
  second: string,
): RelRequirementDraft | undefined {
  const key = pairKey(first, second);
  return draft.decisionModel.relCloseness?.find(
    (relation) =>
      pairKey(relation.firstStationId, relation.secondStationId) === key,
  );
}

export function AdjacenciesStep({
  draft,
  onChange,
}: {
  draft: SrflEditorDraft;
  onChange: (draft: SrflEditorDraft) => void;
}) {
  const [selectedKeys, setSelectedKeys] = useState<readonly string[]>([]);
  const [path, setPath] = useState<string[]>([]);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const existingPairs = useMemo(() => componentPairs(draft), [draft.study.components]);
  const stationNames = useMemo(
    () => new Map(draft.study.stations.map((station) => [station.id, station.name])),
    [draft.study.stations],
  );
  const priorities = useMemo(
    () =>
      (draft.decisionModel.relCloseness ?? []).filter((relation) =>
        ["A", "E", "I", "O"].includes(relation.level),
      ),
    [draft.decisionModel.relCloseness],
  );
  const pathEffects = path.slice(0, -1).map((first, index) => {
    const second = path[index + 1]!;
    return {
      first,
      second,
      relation: relationFor(draft, first, second),
      flow: pairFlow(draft, first, second),
    };
  });

  useEffect(() => {
    if (notice === null) return;
    const timer = window.setTimeout(() => setNotice(null), 3000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const toggle = (id: string) =>
    setPath((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );

  const addPath = (stationIds: string[]) => {
    if (stationIds.length < 2) return;
    const pathKey = stationIds.join("\0");
    const reverseKey = [...stationIds].reverse().join("\0");
    const duplicate = draft.study.components.some((item) => {
      const existing = item.stationIds.join("\0");
      return existing === pathKey || existing === reverseKey;
    });
    if (duplicate) {
      setNotice("Esa restricción ya existe; no se agregó nuevamente.");
      return;
    }
    const base = stationIds.join("-");
    const id = uniqueIdentifier(
      base,
      draft.study.components.map((item) => item.id),
    );
    onChange({
      ...draft,
      study: {
        ...draft.study,
        components: [
          ...draft.study.components,
          {
            clientKey: nextClientKey("component"),
            id,
            idManuallyEdited: false,
            stationIds,
          },
        ],
      },
    });
    setPath([]);
    setSelectedKeys([]);
    setNotice("La relación ya puede participar en las alternativas del estudio.");
  };

  const remove = (clientKey: string) => {
    const item = draft.study.components.find(
      (component) => component.clientKey === clientKey,
    );
    if (item === undefined) return;
    onChange({
      ...draft,
      study: {
        ...draft.study,
        components: draft.study.components.filter(
          (component) => component.clientKey !== clientKey,
        ),
        designs: draft.study.designs.map((design) => ({
          ...design,
          baseComponentIds: design.baseComponentIds.filter(
            (id) => id !== item.id,
          ),
        })),
      },
    });
    setPendingDelete(null);
  };

  const update = (clientKey: string, values: { id?: string }) => {
    const previous = draft.study.components.find(
      (item) => item.clientKey === clientKey,
    );
    if (previous === undefined) return;
    const nextId =
      values.id === undefined
        ? previous.id
        : slugify(values.id, previous.id);
    onChange({
      ...draft,
      study: {
        ...draft.study,
        components: draft.study.components.map((item) =>
          item.clientKey === clientKey
            ? {
                ...item,
                id: nextId,
                idManuallyEdited:
                  values.id !== undefined || item.idManuallyEdited,
              }
            : item,
        ),
        designs: draft.study.designs.map((design) => ({
          ...design,
          baseComponentIds: design.baseComponentIds.map((id) =>
            id === previous.id ? nextId : id,
          ),
        })),
      },
    });
  };

  const target = draft.study.components.find(
    (item) => item.clientKey === pendingDelete,
  );
  const dependencies =
    target === undefined
      ? []
      : draft.study.designs
          .filter((design) => design.baseComponentIds.includes(target.id))
          .map((design) => `Diseño ${design.title}`);
  const flowUnit = draft.decisionModel.adjacencyMatrices[0] ?? null;

  return (
    <section className="srfl-step">
      <div className="srfl-step__intro">
        <h2>Restricciones candidatas</h2>
        <p>
          Definí las cercanías que las alternativas podrán incorporar. Las
          prioridades REL y los movimientos ayudan a elegirlas; no se convierten
          automáticamente en obligaciones.
        </p>
      </div>
      {priorities.length > 0 && (
        <section
          className="srfl-priority-opportunities"
          aria-label="Prioridades REL disponibles"
        >
          <header>
            <div>
              <h3>Prioridades que pueden evaluarse</h3>
              <p>
                Agregá al menos una relación de cada nivel para evitar dimensiones
                que siempre den cero. Después, en Diseños, decidís cuáles son
                obligatorias y cuáles se comparan como candidatas.
              </p>
            </div>
          </header>
          <div className="srfl-priority-grid">
            {priorities.map((relation) => {
              const key = pairKey(
                relation.firstStationId,
                relation.secondStationId,
              );
              const represented = existingPairs.has(key);
              const flow = pairFlow(
                draft,
                relation.firstStationId,
                relation.secondStationId,
              );
              return (
                <article key={key} className={represented ? "is-covered" : ""}>
                  <div>
                    <strong>
                      {stationNames.get(relation.firstStationId) ??
                        relation.firstStationId}{" "}
                      ↔{" "}
                      {stationNames.get(relation.secondStationId) ??
                        relation.secondStationId}
                    </strong>
                    <span>Nivel REL {relation.level}</span>
                  </div>
                  <p>{relation.reason}</p>
                  {flow !== null && flowUnit !== null && (
                    <small>
                      {flow.toLocaleString("es-AR")} {flowUnit.unit}
                      {flowUnit.referencePeriod ? `/${flowUnit.referencePeriod}` : ""}
                    </small>
                  )}
                  {represented ? (
                    <span className="srfl-priority-status">
                      Disponible en las alternativas
                    </span>
                  ) : (
                    <Button
                      variant={ButtonVariant.Secondary}
                      onClick={() =>
                        addPath([
                          relation.firstStationId,
                          relation.secondStationId,
                        ])
                      }
                    >
                      Crear restricción candidata
                    </Button>
                  )}
                </article>
              );
            })}
          </div>
        </section>
      )}
      <div className="srfl-restrictions-layout">
        <section
          className="srfl-restrictions-list"
          aria-label="Lista de restricciones"
        >
          <h3>Restricciones agregadas · {draft.study.components.length}</h3>
          <AdjacencyTable
            expanded={selectedKeys}
            onExpandedChange={setSelectedKeys}
            draft={draft}
            onChange={update}
            onDelete={setPendingDelete}
          />
        </section>
        <aside
          className="srfl-restrictions-tools"
          aria-label="Agregar restricciones"
        >
          <Panel className="srfl-path-builder">
            <h3>Nueva restricción</h3>
            <div className="srfl-path-preview">
              {path.length === 0
                ? "Seleccioná estaciones en el diagrama"
                : path
                    .map((id) => stationNames.get(id) ?? id)
                    .join(" → ")}
            </div>
            {pathEffects.length > 0 && (
              <div className="srfl-path-effects" aria-label="Impacto esperado">
                <strong>Impacto esperado</strong>
                <ul>
                  {pathEffects.map(({ first, second, relation, flow }) => (
                    <li key={pairKey(first, second)}>
                      {stationNames.get(first) ?? first}–
                      {stationNames.get(second) ?? second}: {" "}
                      {relation === undefined
                        ? "sin prioridad REL"
                        : `REL ${relation.level}`}
                      {flow !== null && flowUnit !== null
                        ? ` · ${flow.toLocaleString("es-AR")} ${flowUnit.unit}${flowUnit.referencePeriod ? `/${flowUnit.referencePeriod}` : ""}`
                        : ""}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <Button disabled={path.length < 2} onClick={() => addPath(path)}>
              Agregar restricción candidata
            </Button>
          </Panel>
          <AdjacencyDiagram
            stations={draft.study.stations}
            components={draft.study.components}
            selectedPath={path}
            onToggleStation={toggle}
            onSelectComponents={setSelectedKeys}
          />
        </aside>
      </div>
      {target !== undefined && (
        <DependencyConfirmationModal
          title={`Eliminar ${target.id}`}
          dependencies={
            dependencies.length > 0
              ? dependencies
              : ["No hay diseños dependientes."]
          }
          onClose={() => setPendingDelete(null)}
          onConfirm={() => remove(target.clientKey)}
        />
      )}
      {notice !== null && (
        <div className="srfl-toast srfl-toast--notice" role="status">
          {notice}
        </div>
      )}
    </section>
  );
}
