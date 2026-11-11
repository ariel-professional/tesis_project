import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { useState } from "react";
import { readFileSync } from "node:fs";
import path from "node:path";
import type { AttachmentService, DomainUiHost, FileAttachment, SingleRowFacilityLayoutDraft } from "@domain-ui-sdk";
import { fromScientificDraft, toScientificDraft } from "@srfl-ui/model/mappers";
import { DraftOriginKind } from "@srfl-ui/model/editor-state.types";
import { effectiveEvidence, updateEvidence } from "@srfl-ui/model/evidence";
import { SrflEvidenceField, SrflEvidenceProvider } from "@srfl-ui/components/evidence/SrflEvidence";
import { ExperimentWizard } from "@srfl-ui/components/wizard/ExperimentWizard";
import { StudyInformationStep } from "@srfl-ui/components/wizard/StudyInformationStep";
import { AdjacenciesStep } from "@srfl-ui/components/wizard/AdjacenciesStep";
import { DocumentationPanel } from "@srfl-ui/components/evidence/DocumentationPanel";

afterEach(cleanup);

test("adding a restriction closes details, preserves its text and keeps the detail label stable", () => {
  const initial = fromScientificDraft(definition(), DraftOriginKind.ImportedFile, "Importada");
  function Harness() {
    const [draft, setDraft] = useState(initial);
    return <SrflEvidenceProvider draft={draft} onChange={setDraft}><AdjacenciesStep draft={draft} onChange={setDraft} /></SrflEvidenceProvider>;
  }
  const { container } = render(<Harness />);
  const detail = screen.getAllByRole("button", { name: /Detalle/ })[0]!;
  expect(detail.textContent).toBe("Detalle");
  expect(within(detail).getByRole("img", { name: "Tiene antecedentes" })).toBeTruthy();
  fireEvent.click(detail);
  fireEvent.change(screen.getByRole("textbox", { name: /^Detalle de/ }), { target: { value: "Conservar este motivo" } });
  const stations = container.querySelectorAll(".srfl-diagram__node");
  fireEvent.click(stations[0]!); fireEvent.click(stations[4]!);
  fireEvent.click(screen.getByRole("button", { name: "Agregar restricción candidata" }));
  expect(screen.queryByRole("textbox", { name: /^Detalle de/ })).toBeNull();
  expect(screen.getAllByRole("button", { name: /Detalle/ })).toHaveLength(initial.study.components.length + 1);
  fireEvent.click(detail);
  expect((screen.getByRole("textbox", { name: /^Detalle de/ }) as HTMLTextAreaElement).value).toBe("Conservar este motivo");
});

test("result documentation separates study, designs and the restrictions used by a case", () => {
  const config = definition();
  const component = config.study.components[0]!;
  const design = config.study.designs[0]!;
  render(<DocumentationPanel config={config} componentIds={[component.id]} designId={design.id} />);
  fireEvent.click(screen.getByText("Antecedentes de las decisiones"));
  expect(within(screen.getByRole("region", { name: "Antecedentes: Estudio" })).getByRole("heading", { name: config.study.title })).toBeTruthy();
  expect(within(screen.getByRole("region", { name: "Antecedentes: Diseños" })).getByRole("heading", { name: design.title })).toBeTruthy();
  const restrictions = screen.getByRole("region", { name: "Antecedentes: Restricciones" });
  expect(within(restrictions).getAllByRole("article")).toHaveLength(1);
  expect(within(restrictions).getByRole("heading", { name: `${component.station_ids.join(" → ")} · ${component.id}` })).toBeTruthy();
});
const file: FileAttachment = { kind: "file", sha256: "a".repeat(64), name: "plano.pdf", media_type: "application/pdf", size_bytes: 25 };
const link = { kind: "link" as const, url: "https://example.org/technical", label: "Referencia" };
function definition() {
  const config = JSON.parse(readFileSync(path.resolve(__dirname, "../../../examples/domains/single-row-facility-layout/comparison.json"), "utf8")) as SingleRowFacilityLayoutDraft;
  for (const entity of [config.study, ...config.study.components, ...config.study.designs]) {
    entity.description = "Motivo original";
    entity.attachments = [file, link];
  }
  return config;
}

test.each([[false, false], [true, false], [false, true], [true, true]])("template switches: attachments=%s, restrictions=%s", (importAttachments, importRestrictionDescriptions) => {
  let draft = fromScientificDraft(definition(), DraftOriginKind.Template, "Plantilla");
  expect(draft.templateEvidence).toMatchObject({ importAttachments: false, importRestrictionDescriptions: false });
  draft.templateEvidence = { ...draft.templateEvidence!, importAttachments, importRestrictionDescriptions };
  const config = toScientificDraft(draft);
  expect(config.study.description).toBe("Motivo original");
  expect(config.study.designs[0]!.description).toBe("Motivo original");
  expect(config.study.components[0]!.description ?? "").toBe(importRestrictionDescriptions ? "Motivo original" : "");
  for (const entity of [config.study, ...config.study.components, ...config.study.designs]) expect(entity.attachments ?? []).toEqual(importAttachments ? [file, link] : []);
});

test("own edits survive switch toggles, removals and renaming without resurrecting inherited evidence", () => {
  let draft = fromScientificDraft(definition(), DraftOriginKind.Template, "Plantilla");
  const key = draft.study.components[0]!.clientKey;
  draft.templateEvidence!.importAttachments = true;
  draft = updateEvidence(draft, key, (value) => ({ description: "Motivo propio", attachments: value.attachments.filter((item) => item.kind === "link") }));
  draft.templateEvidence = { ...draft.templateEvidence!, importAttachments: false, importRestrictionDescriptions: false };
  const own = { ...link, url: "https://example.org/new" };
  draft = updateEvidence(draft, key, (value) => ({ ...value, attachments: [...value.attachments, own] }));
  draft.study.components[0]!.id = "renombrada";
  draft.templateEvidence = { ...draft.templateEvidence!, importAttachments: true, importRestrictionDescriptions: true };
  expect(effectiveEvidence(draft, key)).toEqual({ description: "Motivo propio", attachments: [link, own] });
  const config = toScientificDraft(draft);
  expect(config.study.components[0]!.attachments).toEqual([link, own]);
  expect(JSON.stringify(config)).not.toContain("templateEvidence");
});

test("all three owners preserve documentary values through the mapper round-trip", () => {
  const original = definition();
  const draft = fromScientificDraft(original, DraftOriginKind.ImportedFile, "Importada");
  const mapped = toScientificDraft(draft);
  expect(mapped.schema_version).toBe("2.0.0");
  expect(mapped.study.title).toBe(original.study.title);
  expect(mapped.study.components[0]?.description).toBe(original.study.components[0]?.description);
  expect(mapped.study.id).not.toBe(original.study.id);
});

test("shared editor adds a link and file; removing its owner cancels a late upload", async () => {
  let finish!: (value: FileAttachment) => void;
  let signal!: AbortSignal;
  const stage = vi.fn((_file: File, pendingSignal: AbortSignal) => { signal = pendingSignal; return new Promise<FileAttachment>((resolve) => { finish = resolve; }); });
  const service: AttachmentService = { stage, readRange: async () => new Uint8Array(), openLink: async () => {}, documentation: async () => definition(), discardStaged: async () => {} };
  let latest = fromScientificDraft(definition(), DraftOriginKind.ImportedFile, "Importada");
  latest.study.components[0]!.attachments = [];
  const owner = latest.study.components[0]!.clientKey;
  function Harness() {
    const [draft, setDraft] = useState(latest);
    latest = draft;
    return <SrflEvidenceProvider draft={draft} onChange={setDraft} service={service}>{draft.study.components.length > 0 && <SrflEvidenceField owner={owner} />}<button onClick={() => setDraft((current) => ({ ...current, study: { ...current.study, components: [] } }))}>Eliminar entidad</button></SrflEvidenceProvider>;
  }
  render(<Harness />);
  fireEvent.click(screen.getByRole("tab", { name: "URL / Link" }));
  fireEvent.change(screen.getByRole("textbox", { name: "URL" }), { target: { value: link.url } });
  fireEvent.click(screen.getByRole("button", { name: "Agregar enlace" }));
  expect(effectiveEvidence(latest, owner).attachments[0]).toMatchObject({ url: link.url });
  fireEvent.click(screen.getByRole("tab", { name: "Imagen / Plano / PDF" }));
  fireEvent.change(screen.getByLabelText("Seleccionar archivos"), { target: { files: [new File(["%PDF-1.7"], "plano.pdf")] } });
  await waitFor(() => expect(stage).toHaveBeenCalledOnce());
  await act(async () => finish(file));
  expect(effectiveEvidence(latest, owner).attachments).toContainEqual(file);
  fireEvent.change(screen.getByLabelText("Seleccionar archivos"), { target: { files: [new File(["%PDF-1.7"], "otro.pdf")] } });
  fireEvent.click(screen.getByText("Eliminar entidad"));
  expect(signal.aborted).toBe(true);
  await act(async () => finish({ ...file, name: "otro.pdf" }));
  expect(latest.study.components).toEqual([]);
});

test("template switches are rendered off and preserve study text", () => {
  const draft = fromScientificDraft(definition(), DraftOriginKind.Template, "Plantilla");
  render(<StudyInformationStep draft={draft} onChange={() => {}} />);
  for (const control of screen.getAllByRole("switch")) expect(control.getAttribute("aria-checked")).toBe("false");
  expect((screen.getByRole("textbox", { name: "Descripción" }) as HTMLTextAreaElement).value).toBe("Motivo original");
});


test("wizard blocks during transfer and ignores validation from an older revision", async () => {
  let completeUpload!: (value: FileAttachment) => void;
  let rejectOldValidation!: (reason: Error) => void;
  let changeDescription!: () => void;
  const original = fromScientificDraft(definition(), DraftOriginKind.ImportedFile, "Importada");
  const service: AttachmentService = {
    stage: () => new Promise((resolve) => { completeUpload = resolve; }),
    readRange: async () => new Uint8Array(), openLink: async () => {},
    documentation: async () => definition(), discardStaged: async () => {},
  };
  const validate = vi.fn().mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectOldValidation = reject; }))
    .mockImplementation(async (draft: unknown) => ({ valid: true, draft }));
  const host = { attachments: service, validateStudy: validate,
    validateForest: async (draft: unknown) => ({ valid: true, draft }),
    estimateCombinations: async () => ({ theoretical_combinations: 2 }),
  } as unknown as DomainUiHost;
  function Harness() {
    const [state, setState] = useState({ draft: original, revision: 0 });
    changeDescription = () => setState((current) => ({ revision: current.revision + 1, draft: { ...current.draft, study: { ...current.draft.study, description: "Nueva revisión" } } }));
    return <ExperimentWizard host={host} draft={state.draft} revision={state.revision} onChange={(draft) => setState((current) => ({ draft, revision: current.revision + 1 }))} onExit={() => {}} onExecute={() => {}} />;
  }
  render(<Harness />);
  fireEvent.change(screen.getByLabelText("Seleccionar archivos"), { target: { files: [new File(["%PDF-1.7"], "plano.pdf")] } });
  expect((screen.getByRole("button", { name: "Siguiente" }) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => completeUpload(file));
  for (let step = 0; step < 7; step++) await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Siguiente" })); });
  await waitFor(() => expect(validate).toHaveBeenCalledOnce());
  await act(async () => changeDescription());
  await waitFor(() => expect((screen.getByRole("button", { name: "Preparar y ejecutar" }) as HTMLButtonElement).disabled).toBe(false));
  await act(async () => rejectOldValidation(new Error("Obsolete validation failure")));
  expect(screen.queryByText(/Obsolete validation failure/)).toBeNull();
  expect((screen.getByRole("button", { name: "Preparar y ejecutar" }) as HTMLButtonElement).disabled).toBe(false);
});
