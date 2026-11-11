import {
  Button,
  ButtonVariant,
  ActionButton,
  ActionIconButton,
  IconButton,
  MatrixEditor,
  Modal,
  NumberField,
  Panel,
  SelectField,
  SwitchField,
  TextAreaField,
  TextField,
} from "@domain-ui-kit";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import type {
  RelLevel,
  SrflEditorDraft,
  UndesiredCause,
} from "../../model/editor-draft.types";
import { uniqueIdentifier } from "../../model/identifiers";
import {
  buildMatrixEntries,
  canonicalPairKey,
  matrixCellKey,
  type MatrixCell,
} from "../../model/matrix-pairs";
import { matrixExample, parseQuantitativeMatrix, parseRelImport, relListExample, type ImportStation } from "../../model/matrix-import";
import { orderedStations, stationAliases } from "../../model/station-aliases";

const levels: RelLevel[] = ["A", "E", "I", "O", "U", "X"];
const levelOptions = levels.map((value) => ({ value, label: value }));
const causeOptions: { value: UndesiredCause | ""; label: string }[] = [
  { value: "", label: "Seleccionar motivo" },
  { value: "safety", label: "Seguridad" },
  { value: "cross_contamination", label: "Contaminación cruzada" },
  { value: "noise", label: "Ruido" },
  { value: "temperature", label: "Temperatura" },
  { value: "privacy", label: "Privacidad" },
  { value: "interference", label: "Interferencia operativa" },
  { value: "process", label: "Secuencia del proceso" },
];
const nextMatrixId = (matrices: readonly { id: string }[]) => {
  const used = new Set(matrices.map((item) => item.id));
  let candidate = 1;
  while (used.has(String(candidate))) candidate += 1;
  return String(candidate);
};
const decimalPattern = /^-?\d+(?:\.\d+)?$/;
const emptyLevelValues = (): Record<RelLevel, string> => ({
  A: "", E: "", I: "", O: "", U: "", X: "",
});
const compareDecimals = (left: string, right: string) => {
  const width = Math.max(left.split(".")[1]?.length ?? 0, right.split(".")[1]?.length ?? 0);
  const scaled = (value: string) => {
    const negative = value.startsWith("-");
    const [integer = "0", fraction = ""] = (negative ? value.slice(1) : value).split(".");
    const amount = BigInt(integer + fraction.padEnd(width, "0"));
    return negative ? -amount : amount;
  };
  const a = scaled(left); const b = scaled(right);
  return a < b ? -1 : a > b ? 1 : 0;
};

export function RelationsStep({
  draft,
  onChange,
}: {
  draft: SrflEditorDraft;
  onChange: (draft: SrflEditorDraft) => void;
}) {
  const rel = draft.decisionModel.relCloseness;
  const matrices = draft.decisionModel.adjacencyMatrices;
  const [activeMatrixId, setActiveMatrixId] = useState(matrices[0]?.id ?? "");
  const flow = matrices.find((item) => item.id === activeMatrixId) ?? matrices[0] ?? null;
  const [tab, setTab] = useState<"rel" | "flow">(rel !== null ? "rel" : "flow");
  const [relView, setRelView] = useState<"matrix" | "list">("matrix");
  const [flowView, setFlowView] = useState<"matrix" | "list">("matrix");
  const [editingRel, setEditingRel] = useState<MatrixCell | null>(null);
  const [selectedRel, setSelectedRel] = useState<readonly MatrixCell[]>([]);
  const [selectedFlow, setSelectedFlow] = useState<readonly MatrixCell[]>([]);
  const [editingFlow, setEditingFlow] = useState<MatrixCell | null>(null);
  const [flowEditValue, setFlowEditValue] = useState("");
  const [flowEditError, setFlowEditError] = useState<string | undefined>();
  const skipFlowBlurCommit = useRef(false);
  const [bulkRelLevel, setBulkRelLevel] = useState<RelLevel | "">("");
  const [bulkFlowValue, setBulkFlowValue] = useState("");
  const [bulkFlowError, setBulkFlowError] = useState<string | null>(null);
  const [relMatrixId, setRelMatrixId] = useState(matrices[0]?.id ?? "");
  const [relLevelValues, setRelLevelValues] = useState<Record<RelLevel, string>>(emptyLevelValues);
  const [unassignedPenalty, setUnassignedPenalty] = useState("");
  const [relMappingError, setRelMappingError] = useState<string | null>(null);
  const [paste, setPaste] = useState("");
  const [sharedReason, setSharedReason] = useState("");
  const [sharedSource, setSharedSource] = useState("");
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [showImportHelp, setShowImportHelp] = useState(false);
  const [relHelpFormat, setRelHelpFormat] = useState<"list" | "matrix">("list");
  const [copyNotice, setCopyNotice] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  const aliases = stationAliases(draft.study.stations);
  const displayedStations = orderedStations(draft.study.stations, draft.study.stationDisplayOrder);
  const importStations: ImportStation[] = displayedStations.map((item) => ({ clientKey: item.clientKey, id: item.id, alias: aliases.get(item.clientKey) ?? item.id, name: item.name }));
  const stations = displayedStations.map((item) => ({
    id: item.id,
    label: item.name || item.id,
  }));
  const updateDecision = (decisionModel: SrflEditorDraft["decisionModel"]) =>
    onChange({ ...draft, decisionModel });
  useEffect(() => {
    if (flow !== null && flow.id !== activeMatrixId) setActiveMatrixId(flow.id);
  }, [activeMatrixId, flow]);
  useEffect(() => {
    if (!matrices.some((matrix) => matrix.id === relMatrixId)) setRelMatrixId(matrices[0]?.id ?? "");
  }, [matrices, relMatrixId]);
  const stationSignature = stations.map((station) => station.id).join("\0");
  useEffect(() => {
    setSelectedRel([]); setSelectedFlow([]); setEditingRel(null); setEditingFlow(null);
  }, [activeMatrixId, relView, flowView, stationSignature]);
  const replaceMatrix = (matrixId: string, next: NonNullable<typeof flow>) => updateDecision({
    ...draft.decisionModel,
    adjacencyMatrices: matrices.map((item) => item.id === matrixId ? next : item),
  });
  const replaceFlow = (next: NonNullable<typeof flow>) => {
    if (flow !== null) replaceMatrix(flow.id, next);
  };
  const relIndex = (a: string, b: string) =>
    rel?.findIndex(
      (item) => canonicalPairKey(item.firstStationId, item.secondStationId) ===
        canonicalPairKey(a, b),
    ) ?? -1;
  const flowIndex = (a: string, b: string) =>
    flow?.entries.findIndex(
      (item) =>
        (item.fromStationId === a && item.toStationId === b) ||
        (!flow.directed && item.fromStationId === b && item.toStationId === a),
    ) ?? -1;
  const updateRel = (
    index: number,
    field: "level" | "reason" | "provenance",
    value: string,
  ) => {
    if (rel === null || index < 0) return;
    const current = rel[index];
    const removesX =
      field === "level" && current?.level === "X" && value !== "X";
    updateDecision({
      ...draft.decisionModel,
      relCloseness: rel.map((item, i) =>
        i === index ? { ...item, [field]: value } : item,
      ),
      undesiredPrescribedAdjacencies:
        removesX && current !== undefined
          ? draft.decisionModel.undesiredPrescribedAdjacencies.filter(
              (item) => canonicalPairKey(item.firstStationId, item.secondStationId) !==
                canonicalPairKey(current.firstStationId, current.secondStationId),
            )
          : draft.decisionModel.undesiredPrescribedAdjacencies,
    });
  };
  const updateFlow = (index: number, value: string) => {
    if (flow !== null && index >= 0)
      replaceFlow({
          ...flow,
          entries: flow.entries.map((item, i) =>
            i === index ? { ...item, value } : item,
          ),
      });
  };
  const toggleCell = (
    setter: (value: readonly MatrixCell[] | ((current: readonly MatrixCell[]) => readonly MatrixCell[])) => void,
    rowId: string,
    columnId: string,
  ) => setter((current) => current.some((cell) => cell.rowId === rowId && cell.columnId === columnId)
    ? current.filter((cell) => cell.rowId !== rowId || cell.columnId !== columnId)
    : [...current, { rowId, columnId }]);
  const removeCell = (
    setter: (value: readonly MatrixCell[] | ((current: readonly MatrixCell[]) => readonly MatrixCell[])) => void,
    rowId: string,
    columnId: string,
  ) => setter((current) => current.filter((cell) => cell.rowId !== rowId || cell.columnId !== columnId));
  const applySelectedRel = () => {
    if (rel === null || selectedRel.length === 0) return;
    const selectedKeys = new Set(selectedRel.map((cell) => canonicalPairKey(cell.rowId, cell.columnId)));
    const nextRel = rel.map((item) => selectedKeys.has(canonicalPairKey(item.firstStationId, item.secondStationId))
      ? {
          ...item,
          ...(bulkRelLevel !== "" ? { level: bulkRelLevel } : {}),
          ...(sharedReason.trim() !== "" ? { reason: sharedReason } : {}),
          ...(sharedSource.trim() !== "" ? { provenance: sharedSource } : {}),
        }
      : item);
    const removedX = new Set(rel.filter((item) =>
      item.level === "X"
      && bulkRelLevel !== ""
      && bulkRelLevel !== "X"
      && selectedKeys.has(canonicalPairKey(item.firstStationId, item.secondStationId)))
      .map((item) => canonicalPairKey(item.firstStationId, item.secondStationId)));
    updateDecision({
      ...draft.decisionModel,
      relCloseness: nextRel,
      undesiredPrescribedAdjacencies: draft.decisionModel.undesiredPrescribedAdjacencies.filter(
        (item) => !removedX.has(canonicalPairKey(item.firstStationId, item.secondStationId)),
      ),
    });
    setSelectedRel([]);
  };
  const applySelectedFlow = () => {
    if (flow === null || selectedFlow.length === 0) return;
    if (!decimalPattern.test(bulkFlowValue)) {
      setBulkFlowError("Ingresá un decimal válido.");
      return;
    }
    const selectedKeys = new Set(selectedFlow.map((cell) => matrixCellKey(cell.rowId, cell.columnId, flow.directed)));
    replaceFlow({
      ...flow,
      entries: flow.entries.map((entry) => selectedKeys.has(matrixCellKey(entry.fromStationId, entry.toStationId, flow.directed))
        ? { ...entry, value: bulkFlowValue }
        : entry),
    });
    setBulkFlowError(null);
    setSelectedFlow([]);
  };
  const beginFlowEdit = (rowId: string, columnId: string) => {
    const index = flowIndex(rowId, columnId);
    if (index < 0 || flow === null) return;
    removeCell(setSelectedFlow, rowId, columnId);
    setEditingFlow({ rowId, columnId });
    setFlowEditValue(flow.entries[index]?.value ?? "");
    setFlowEditError(undefined);
    skipFlowBlurCommit.current = false;
  };
  const commitFlowEdit = () => {
    if (skipFlowBlurCommit.current) { skipFlowBlurCommit.current = false; return; }
    if (editingFlow === null) return;
    if (!decimalPattern.test(flowEditValue)) {
      setFlowEditError("Ingresá un decimal válido.");
      return;
    }
    skipFlowBlurCommit.current = true;
    updateFlow(flowIndex(editingFlow.rowId, editingFlow.columnId), flowEditValue);
    setEditingFlow(null);
    setFlowEditError(undefined);
  };
  const applyRelMapping = () => {
    if (rel === null) return;
    const target = matrices.find((matrix) => matrix.id === relMatrixId);
    if (target === undefined) {
      setRelMappingError("Seleccioná una matriz cuantitativa.");
      return;
    }
    const explicitValues = Object.values(relLevelValues).filter((value) => value !== "");
    if (explicitValues.some((value) => !decimalPattern.test(value))) {
      setRelMappingError("Los valores por nivel deben ser decimales válidos.");
      return;
    }
    if (target.direction === "minimize") {
      if (!decimalPattern.test(unassignedPenalty)) {
        setRelMappingError("Ingresá un valor finito para los niveles sin asignar.");
        return;
      }
      if (explicitValues.some((value) => compareDecimals(unassignedPenalty, value) <= 0)) {
        setRelMappingError("El valor para niveles sin asignar debe ser mayor que todos los valores declarados.");
        return;
      }
    }
    const levelByPair = new Map(rel.map((item) => [
      canonicalPairKey(item.firstStationId, item.secondStationId),
      item.level,
    ]));
    const fallback = target.direction === "maximize" ? "0" : unassignedPenalty;
    replaceMatrix(target.id, {
      ...target,
      entries: target.entries.map((entry) => {
        const level = levelByPair.get(canonicalPairKey(entry.fromStationId, entry.toStationId));
        return { ...entry, value: level === undefined ? fallback : relLevelValues[level] || fallback };
      }),
    });
    setRelMappingError(null);
  };
  const setDirected = (directed: boolean) => {
    if (flow === null) return;
    const ids = stations.map((item) => item.id);
    const value = (a: string, b: string) =>
      flow.entries.find(
        (item) =>
          (item.fromStationId === a && item.toStationId === b) ||
          (item.fromStationId === b && item.toStationId === a),
      )?.value ?? "0";
    const entries = buildMatrixEntries(ids, directed, value);
    replaceFlow({ ...flow, directed, entries });
  };
  const importRows = (raw: string) => {
    try {
      if (tab === "rel" && rel !== null) {
        const imported = parseRelImport(raw, importStations);
        const byPair = imported.kind === "rel-list"
          ? new Map(imported.rows.map((item) => [canonicalPairKey(item.firstStationId, item.secondStationId), item]))
          : imported.levels;
        const nextRel = rel.map((item) => {
          const value = byPair.get(canonicalPairKey(item.firstStationId, item.secondStationId));
          if (value === undefined) return item;
          return typeof value === "string" ? { ...item, level: value } : { ...item, ...value };
        });
        const removedPolicies = new Set(rel.filter((item, index) => item.level === "X" && nextRel[index]?.level !== "X").map((item) => canonicalPairKey(item.firstStationId, item.secondStationId)));
        onChange({
          ...draft,
          study: imported.kind === "rel-matrix" ? { ...draft.study, stationDisplayOrder: imported.stationDisplayOrder } : draft.study,
          decisionModel: {
            ...draft.decisionModel,
            relCloseness: nextRel,
            undesiredPrescribedAdjacencies: draft.decisionModel.undesiredPrescribedAdjacencies.filter((item) => !removedPolicies.has(canonicalPairKey(item.firstStationId, item.secondStationId))),
          },
        });
      } else if (flow !== null) {
        const imported = parseQuantitativeMatrix(raw, importStations);
        onChange({
          ...draft,
          study: { ...draft.study, stationDisplayOrder: imported.stationDisplayOrder },
          decisionModel: { ...draft.decisionModel, adjacencyMatrices: matrices.map((matrix) => matrix.id === flow.id ? { ...matrix, directed: imported.directed, entries: imported.entries } : matrix) },
        });
      }
      setImportError(null);
    } catch (error) {
      setImportError(error instanceof Error ? error.message : "No se pudieron importar los datos.");
    }
  };
  const createMatrix = () => {
    const id = nextMatrixId(matrices);
    const name = uniqueIdentifier(`Matriz ${id}`, matrices.map((item) => item.name));
    const entries = buildMatrixEntries(stations.map((station) => station.id), true);
    updateDecision({ ...draft.decisionModel, adjacencyMatrices: [...matrices, { id, name, description: "", direction: "maximize", unit: "", referencePeriod: "", provenance: "", directed: true, entries }] });
    setActiveMatrixId(id);
  };
  const duplicateMatrix = () => {
    if (flow === null) return;
    const id = nextMatrixId(matrices);
    const name = uniqueIdentifier(`${flow.name} copia`, matrices.map((item) => item.name));
    updateDecision({ ...draft.decisionModel, adjacencyMatrices: [...matrices, { ...structuredClone(flow), id, name }] });
    setActiveMatrixId(id);
  };
  const removeMatrix = (id: string) => {
    const remaining = matrices.filter((item) => item.id !== id);
    updateDecision({
      ...draft.decisionModel,
      adjacencyMatrices: remaining,
      selectedObjectives: remaining.length === 0 ? draft.decisionModel.selectedObjectives.filter((item) => item.id !== "captured-adjacency-flow") : draft.decisionModel.selectedObjectives,
    });
    setActiveMatrixId(remaining[0]?.id ?? "");
    setPendingDelete(null);
  };
  const loadCsv = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file !== undefined)
      void file.text().then((text) => {
        setPaste(text);
        importRows(text);
      });
    event.target.value = "";
  };
  const relValue = (fromId: string, toId: string) => rel?.find((item) => canonicalPairKey(item.firstStationId, item.secondStationId) === canonicalPairKey(fromId, toId))?.level ?? "U";
  const flowValue = (fromId: string, toId: string) => {
    if (flow === null) return "0";
    return flow.entries.find((item) => item.fromStationId === fromId && item.toStationId === toId)?.value
      ?? flow.entries.find((item) => !flow.directed && item.fromStationId === toId && item.toStationId === fromId)?.value
      ?? "0";
  };
  const importExample = tab === "rel"
    ? relHelpFormat === "list" ? relListExample(importStations, rel ?? []) : matrixExample(importStations, relValue)
    : matrixExample(importStations, flowValue);
  const fallbackCopy = (text: string) => {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    const copied = typeof document.execCommand === "function" && document.execCommand("copy");
    area.remove();
    if (!copied) throw new Error("No se pudo copiar el ejemplo.");
  };
  const copyExample = () => {
    let copy: Promise<void>;
    try {
      fallbackCopy(importExample);
      copy = Promise.resolve();
    } catch {
      copy = navigator.clipboard?.writeText(importExample) ?? Promise.reject(new Error("No hay un mecanismo de copia disponible"));
    }
    void copy
      .then(() => {
      setCopyError(null);
      setCopyNotice(true);
      window.setTimeout(() => setCopyNotice(false), 2000);
      })
      .catch(() => setCopyError("No se pudo copiar. Seleccioná el ejemplo y copialo manualmente."));
  };
  const xPairs = rel?.filter((item) => item.level === "X") ?? [];
  const setPolicy = (
    first: string,
    second: string,
    policy: "forbidden" | "warn",
  ) => {
    const existing = draft.decisionModel.undesiredPrescribedAdjacencies.find(
      (item) =>
        item.firstStationId === first && item.secondStationId === second,
    );
    const rest = draft.decisionModel.undesiredPrescribedAdjacencies.filter(
      (item) =>
        item.firstStationId !== first || item.secondStationId !== second,
    );
    updateDecision({
      ...draft.decisionModel,
      undesiredPrescribedAdjacencies: [
        ...rest,
        existing === undefined
          ? {
              firstStationId: first,
              secondStationId: second,
              cause: "",
              explanation: "",
              provenance: "",
              policy,
            }
          : { ...existing, policy },
      ],
    });
  };
  const updatePolicy = (
    first: string,
    second: string,
    field: "cause" | "explanation" | "provenance",
    value: string,
  ) =>
    updateDecision({
      ...draft.decisionModel,
      undesiredPrescribedAdjacencies:
        draft.decisionModel.undesiredPrescribedAdjacencies.map((item) =>
          item.firstStationId === first && item.secondStationId === second
            ? { ...item, [field]: value }
            : item,
        ),
    });
  const activeRelIndex =
    editingRel === null ? -1 : relIndex(editingRel.rowId, editingRel.columnId);
  if (rel === null && flow === null)
    return (
      <section className="srfl-step">
        <h2>Datos de relaciones</h2>
        <Panel>
          <p>
            Los criterios seleccionados no requieren matrices de relaciones.
          </p>
        </Panel>
      </section>
    );
  return (
    <section className="srfl-step">
      <div className="srfl-step__intro">
        <h2>Datos de relaciones</h2>
        <p>
          Definí prioridades de cercanía y valores cuantitativos. Las tablas
          se actualizan automáticamente cuando cambian las estaciones.
        </p>
      </div>
      <div
        className="srfl-relation-tabs"
        role="tablist"
        aria-label="Tipo de datos de relaciones"
      >
        {rel !== null && (
          <Button
            variant={tab === "rel" ? undefined : ButtonVariant.Secondary}
            role="tab"
            aria-selected={tab === "rel"}
            onClick={() => setTab("rel")}
          >
            Prioridades de cercanía
          </Button>
        )}
        {flow !== null && (
          <Button
            variant={tab === "flow" ? undefined : ButtonVariant.Secondary}
            role="tab"
            aria-selected={tab === "flow"}
            onClick={() => setTab("flow")}
          >
            Matrices cuantitativas ({matrices.length})
          </Button>
        )}
      </div>
      {tab === "rel" && rel !== null && (
        <div role="tabpanel" className="srfl-relation-panel">
          <header>
            <div>
              <h3>Prioridades de cercanía (REL)</h3>
              <p>
                Clasificá cada par: A es la prioridad más alta y X indica una
                cercanía indeseada.
              </p>
            </div>
            <ViewSwitch value={relView} onChange={setRelView} />
          </header>
          <Panel className="srfl-bulk-fields">
            <h4>Editar celdas seleccionadas</h4>
            <SelectField
              label="Prioridad de cercanía"
              helperText={`${selectedRel.length} ${selectedRel.length === 1 ? "celda seleccionada" : "celdas seleccionadas"}.`}
              value={bulkRelLevel}
              options={[{ value: "", label: "No cambiar" }, ...levelOptions]}
              onChange={(event) => setBulkRelLevel(event.target.value as RelLevel | "")}
            />
            <TextField
              label="Motivo operativo"
              value={sharedReason}
              onChange={(event) => setSharedReason(event.target.value)}
            />
            <TextField
              label="Fuente del dato"
              value={sharedSource}
              onChange={(event) => setSharedSource(event.target.value)}
            />
            <Button
              variant={ButtonVariant.Secondary}
              disabled={selectedRel.length === 0 || (bulkRelLevel === "" && !sharedReason.trim() && !sharedSource.trim())}
              onClick={applySelectedRel}
            >
              Aplicar a campos seleccionados
            </Button>
          </Panel>
          {matrices.length > 0 && <Panel className="srfl-rel-values">
            <div className="srfl-rel-values__heading">
              <div><h4>Completar una matriz desde REL</h4><p>Asigna cada valor por nivel a todas las relaciones de la matriz elegida.</p></div>
              <SelectField
                label="Matriz cuantitativa"
                value={relMatrixId}
                options={matrices.map((matrix) => ({ value: matrix.id, label: `${matrix.name} · ${matrix.direction === "maximize" ? "Maximizar" : "Minimizar"}` }))}
                onChange={(event) => { setRelMatrixId(event.target.value); setRelMappingError(null); }}
              />
            </div>
            <div className="srfl-rel-values__levels">
              {levels.map((level) => <NumberField
                key={level}
                step="any"
                label={`Nivel ${level}`}
                value={relLevelValues[level]}
                onChange={(event) => setRelLevelValues((current) => ({ ...current, [level]: event.target.value }))}
              />)}
            </div>
            {matrices.find((matrix) => matrix.id === relMatrixId)?.direction === "minimize" && <NumberField
              step="any"
              label="Valor para niveles sin asignar"
              description="Debe ser mayor que los valores declarados."
              value={unassignedPenalty}
              onChange={(event) => setUnassignedPenalty(event.target.value)}
            />}
            {relMappingError !== null && <p role="alert" className="ui-field__error">{relMappingError}</p>}
            <Button variant={ButtonVariant.Secondary} onClick={applyRelMapping}>Aplicar valores a la matriz</Button>
          </Panel>}
          {relView === "matrix" ? (
            <>
              <MatrixEditor
                rows={stations}
                mode="triangular"
                label="Matriz de prioridades REL"
                selectedCells={selectedRel}
                onToggleCell={(rowId, columnId) => toggleCell(setSelectedRel, rowId, columnId)}
                onEditCell={(rowId, columnId) => {
                  removeCell(setSelectedRel, rowId, columnId);
                  setEditingRel({ rowId, columnId });
                }}
                renderCell={(a, b) => rel[relIndex(a, b)]?.level ?? "—"}
              />
              {activeRelIndex >= 0 && (
                <Panel className="srfl-cell-editor">
                  <h4>
                    {editingRel?.rowId} · {editingRel?.columnId}
                  </h4>
                  <SelectField
                    label="Prioridad de cercanía"
                    value={rel[activeRelIndex]!.level}
                    options={levelOptions}
                    onChange={(event) =>
                      updateRel(activeRelIndex, "level", event.target.value)
                    }
                  />
                  <TextField
                    label="Motivo operativo"
                    value={rel[activeRelIndex]!.reason}
                    onChange={(event) =>
                      updateRel(activeRelIndex, "reason", event.target.value)
                    }
                  />
                  <TextField
                    label="Fuente del dato"
                    value={rel[activeRelIndex]!.provenance}
                    onChange={(event) =>
                      updateRel(
                        activeRelIndex,
                        "provenance",
                        event.target.value,
                      )
                    }
                  />
                </Panel>
              )}
            </>
          ) : (
            <RelList rel={rel} updateRel={updateRel} />
          )}
          <section className="srfl-policy-section">
            <h3>Tratamiento de cercanías indeseadas (nivel X)</h3>
            <p>
              Elegí si deben advertirse o excluir alternativas que las
              conviertan en obligatorias.
            </p>
            {xPairs.length === 0 ? (
              <p>No hay pares con nivel X.</p>
            ) : (
              <div className="srfl-policy-grid">
                {xPairs.map((pair) => {
                  const policy =
                    draft.decisionModel.undesiredPrescribedAdjacencies.find(
                      (item) =>
                        item.firstStationId === pair.firstStationId &&
                        item.secondStationId === pair.secondStationId,
                    );
                  return (
                    <Panel
                      key={`${pair.firstStationId}-${pair.secondStationId}`}
                    >
                      <h4>
                        {pair.firstStationId} · {pair.secondStationId}
                      </h4>
                      {policy === undefined ? (
                        <div className="srfl-button-row">
                          <Button
                            variant={ButtonVariant.Secondary}
                            onClick={() =>
                              setPolicy(
                                pair.firstStationId,
                                pair.secondStationId,
                                "warn",
                              )
                            }
                          >
                            Sólo advertir
                          </Button>
                          <Button
                            onClick={() =>
                              setPolicy(
                                pair.firstStationId,
                                pair.secondStationId,
                                "forbidden",
                              )
                            }
                          >
                            Excluir alternativa
                          </Button>
                        </div>
                      ) : (
                        <>
                          <SelectField
                            label="Tratamiento"
                            value={policy.policy}
                            options={[
                              { value: "warn", label: "Advertir" },
                              {
                                value: "forbidden",
                                label: "Excluir alternativa",
                              },
                            ]}
                            onChange={(event) =>
                              setPolicy(
                                pair.firstStationId,
                                pair.secondStationId,
                                event.target.value as "warn" | "forbidden",
                              )
                            }
                          />
                          <SelectField
                            label="Motivo principal"
                            value={policy.cause}
                            options={causeOptions}
                            onChange={(event) =>
                              updatePolicy(
                                pair.firstStationId,
                                pair.secondStationId,
                                "cause",
                                event.target.value,
                              )
                            }
                          />
                          <TextField
                            label="Justificación concreta"
                            value={policy.explanation}
                            onChange={(event) =>
                              updatePolicy(
                                pair.firstStationId,
                                pair.secondStationId,
                                "explanation",
                                event.target.value,
                              )
                            }
                          />
                          <TextField
                            label="Fuente de la decisión"
                            value={policy.provenance}
                            onChange={(event) =>
                              updatePolicy(
                                pair.firstStationId,
                                pair.secondStationId,
                                "provenance",
                                event.target.value,
                              )
                            }
                          />
                        </>
                      )}
                    </Panel>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}
      {tab === "flow" && flow !== null && (
        <div role="tabpanel" className="srfl-relation-panel">
          <header>
            <div>
              <h3>Matrices cuantitativas</h3>
              <p>Cada matriz mide una dimensión independiente para comparar alternativas.</p>
            </div>
            <div className="srfl-flow-actions">
              <ViewSwitch value={flowView} onChange={setFlowView} />
              <ActionButton action="duplicate" label="Duplicar matriz" variant={ButtonVariant.Secondary} onClick={duplicateMatrix} />
              <ActionIconButton action="delete" label={`Eliminar ${flow.name}`} onClick={() => setPendingDelete(flow.id)} />
            </div>
          </header>
          <div className="srfl-matrix-tabs" role="tablist" aria-label="Matrices cargadas">
            {matrices.map((matrix) => <Button
              key={matrix.id}
              role="tab"
              aria-selected={matrix.id === flow.id}
              aria-controls={`matrix-panel-${matrix.id}`}
              variant={matrix.id === flow.id ? ButtonVariant.Primary : ButtonVariant.Secondary}
              onClick={() => setActiveMatrixId(matrix.id)}
            >
              <span>{matrix.name}</span>
              <small>{matrix.direction === "maximize" ? "↑ Maximizar" : "↓ Minimizar"}</small>
            </Button>)}
            <IconButton className="srfl-matrix-tabs__add" label="Agregar matriz" onClick={createMatrix}><span aria-hidden="true">+</span></IconButton>
          </div>
          <section id={`matrix-panel-${flow.id}`} role="tabpanel" aria-label={flow.name} className="srfl-matrix-panel">
          <div className="srfl-flow-settings">
            <div className="srfl-flow-settings__primary">
              <TextField label="Nombre (*)" value={flow.name} onChange={(event) => replaceFlow({ ...flow, name: event.target.value })} />
              <SelectField label="Objetivo" value={flow.direction} options={[{ value: "maximize", label: "Maximizar" }, { value: "minimize", label: "Minimizar" }]} onChange={(event) => replaceFlow({ ...flow, direction: event.target.value as "maximize" | "minimize" })} />
              <TextField label="Unidad" helperText="Ej.: viajes, ARS, incidentes o puntos." value={flow.unit} onChange={(event) => replaceFlow({ ...flow, unit: event.target.value })} />
              <TextField label="Período de referencia (opcional)" helperText="Ej.: por turno, día o semana." value={flow.referencePeriod} onChange={(event) => replaceFlow({ ...flow, referencePeriod: event.target.value })} />
              <TextField label="Fuente de los datos (*)" helperText="Ej.: ERP, medición, presupuesto o estimación." value={flow.provenance} onChange={(event) => replaceFlow({ ...flow, provenance: event.target.value })} />
            </div>
            <div className="srfl-flow-settings__description">
              <TextAreaField label="Qué representa (*)" rows={3} value={flow.description} onChange={(event) => replaceFlow({ ...flow, description: event.target.value })} />
            </div>
            <SwitchField
              label="Distinguir dirección"
              description="Activá si A → B puede diferir de B → A."
              checked={flow.directed}
              onChange={setDirected}
            />
          </div>
          {flowView === "matrix" ? (
            <>
              <Panel className="srfl-bulk-fields srfl-bulk-fields--compact">
                <h4>Editar celdas seleccionadas</h4>
                <NumberField
                  step="any"
                  label="Valor"
                  helperText={`${selectedFlow.length} ${selectedFlow.length === 1 ? "celda seleccionada" : "celdas seleccionadas"}.`}
                  error={bulkFlowError ?? undefined}
                  value={bulkFlowValue}
                  onChange={(event) => { setBulkFlowValue(event.target.value); setBulkFlowError(null); }}
                />
                <Button variant={ButtonVariant.Secondary} disabled={selectedFlow.length === 0} onClick={applySelectedFlow}>Aplicar a campos seleccionados</Button>
              </Panel>
              <MatrixEditor
                rows={stations}
                mode={flow.directed ? "full" : "triangular"}
                label={`Matriz ${flow.name}`}
                selectedCells={selectedFlow}
                editingCell={editingFlow}
                onToggleCell={(rowId, columnId) => toggleCell(setSelectedFlow, rowId, columnId)}
                onEditCell={beginFlowEdit}
                renderCell={(a, b) => flow.entries[flowIndex(a, b)]?.value ?? "—"}
                renderEditor={(a, b) => {
                  const from = stations.find((station) => station.id === a)?.label ?? a;
                  const to = stations.find((station) => station.id === b)?.label ?? b;
                  return <NumberField
                    autoFocus
                    step="any"
                    label={`${flow.name}: ${from} → ${to}`}
                    error={flowEditError}
                    value={flowEditValue}
                    onChange={(event) => { setFlowEditValue(event.target.value); setFlowEditError(undefined); }}
                    onBlur={commitFlowEdit}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") { event.preventDefault(); commitFlowEdit(); }
                      if (event.key === "Escape") { event.preventDefault(); skipFlowBlurCommit.current = true; setEditingFlow(null); setFlowEditError(undefined); }
                    }}
                  />;
                }}
              />
            </>
          ) : (
            <FlowList flow={flow} updateFlow={updateFlow} />
          )}
          </section>
        </div>
      )}
      {pendingDelete !== null && <Modal title="Eliminar matriz" onClose={() => setPendingDelete(null)} actions={<><Button variant={ButtonVariant.Secondary} onClick={() => setPendingDelete(null)}>Conservar</Button><Button variant={ButtonVariant.Danger} onClick={() => removeMatrix(pendingDelete)}>Eliminar matriz</Button></>}><p>Se eliminarán sus metadatos y todos los valores cargados. Si es la última matriz, también se deseleccionará el criterio.</p></Modal>}
      <details className="srfl-import-panel">
        <summary>Importar CSV o texto tabulado</summary>
        <div className="srfl-import-panel__heading">
          <p>{tab === "rel" ? "Importá una lista REL o una matriz mediante los alias." : "Importá una matriz completa mediante los alias."}</p>
          <IconButton label="Ver formatos y ejemplos de importación" onClick={() => setShowImportHelp(true)}>ⓘ</IconButton>
        </div>
        {importError !== null && <p role="alert" className="ui-field__error">{importError}</p>}
        <TextAreaField
          label="Datos tabulares"
          value={paste}
          placeholder={tab === "rel" ? "Pegá la lista REL o la matriz con alias." : "Pegá la matriz cuantitativa con alias."}
          onChange={(event) => setPaste(event.target.value)}
        />
        <div className="srfl-button-row">
          <Button
            variant={ButtonVariant.Secondary}
            onClick={() => importRows(paste)}
          >
            Aplicar datos
          </Button>
          <label className="ui-button ui-button--secondary">
            Elegir archivo CSV
            <input
              className="sr-only"
              type="file"
              accept=".csv,text/csv,text/plain"
              onChange={loadCsv}
            />
          </label>
        </div>
      </details>
      {showImportHelp && <Modal
        title={tab === "rel" ? "Formatos de importación REL" : `Importar ${flow?.name ?? "matriz cuantitativa"}`}
        onClose={() => setShowImportHelp(false)}
        actions={<><ActionButton action="copy" label="Copiar ejemplo" variant={ButtonVariant.Secondary} onClick={copyExample} /><Button onClick={() => setShowImportHelp(false)}>Cerrar</Button></>}
      >
        {tab === "rel" && <div className="srfl-view-switch" aria-label="Formato del ejemplo">
          <Button variant={relHelpFormat === "list" ? undefined : ButtonVariant.Secondary} onClick={() => setRelHelpFormat("list")}>Lista de relaciones</Button>
          <Button variant={relHelpFormat === "matrix" ? undefined : ButtonVariant.Secondary} onClick={() => setRelHelpFormat("matrix")}>Matriz</Button>
        </div>}
        <p>{tab === "rel" && relHelpFormat === "list" ? "La lista puede actualizar sólo las relaciones declaradas; motivo operativo y fuente pueden quedar vacíos." : "La primera fila y la primera columna contienen todos los alias."}</p>
        <pre className="srfl-import-example" tabIndex={0}>{importExample}</pre>
        {copyNotice && <p role="status">Ejemplo copiado.</p>}
        {copyError !== null && <p role="alert" className="ui-field__error">{copyError}</p>}
      </Modal>}
    </section>
  );
}

function ViewSwitch({
  value,
  onChange,
}: {
  value: "matrix" | "list";
  onChange: (value: "matrix" | "list") => void;
}) {
  return (
    <div className="srfl-view-switch" aria-label="Vista">
      <Button
        variant={value === "matrix" ? undefined : ButtonVariant.Secondary}
        onClick={() => onChange("matrix")}
      >
        Matriz
      </Button>
      <Button
        variant={value === "list" ? undefined : ButtonVariant.Secondary}
        onClick={() => onChange("list")}
      >
        Lista
      </Button>
    </div>
  );
}
function RelList({
  rel,
  updateRel,
}: {
  rel: NonNullable<SrflEditorDraft["decisionModel"]["relCloseness"]>;
  updateRel: (
    index: number,
    field: "level" | "reason" | "provenance",
    value: string,
  ) => void;
}) {
  return (
    <div className="ui-table-wrap">
      <table className="ui-table">
        <thead>
          <tr>
            <th>Áreas</th>
            <th>Prioridad</th>
            <th>Motivo operativo</th>
            <th>Fuente del dato</th>
          </tr>
        </thead>
        <tbody>
          {rel.map((item, index) => (
            <tr key={`${item.firstStationId}-${item.secondStationId}`}>
              <td>
                {item.firstStationId} · {item.secondStationId}
              </td>
              <td>
                <SelectField
                  label="Prioridad"
                  aria-label={`Prioridad ${item.firstStationId} ${item.secondStationId}`}
                  value={item.level}
                  options={levelOptions}
                  onChange={(event) =>
                    updateRel(index, "level", event.target.value)
                  }
                />
              </td>
              <td>
                <TextField
                  label="Motivo"
                  value={item.reason}
                  onChange={(event) =>
                    updateRel(index, "reason", event.target.value)
                  }
                />
              </td>
              <td>
                <TextField
                  label="Fuente"
                  value={item.provenance}
                  onChange={(event) =>
                    updateRel(index, "provenance", event.target.value)
                  }
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function FlowList({
  flow,
  updateFlow,
}: {
  flow: SrflEditorDraft["decisionModel"]["adjacencyMatrices"][number];
  updateFlow: (index: number, value: string) => void;
}) {
  return (
    <div className="ui-table-wrap">
      <table className="ui-table">
        <thead>
          <tr>
            <th>Origen</th>
            <th>Destino</th>
            <th>Valor</th>
          </tr>
        </thead>
        <tbody>
          {flow.entries.map((item, index) => (
            <tr key={`${item.fromStationId}-${item.toStationId}`}>
              <td>{item.fromStationId}</td>
              <td>{item.toStationId}</td>
              <td>
                <NumberField
                  step="any"
                  label="Valor"
                  value={item.value}
                  onChange={(event) => updateFlow(index, event.target.value)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
