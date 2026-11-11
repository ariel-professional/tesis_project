import { AppSidebar, Button, ButtonVariant, Modal, type SidebarItem } from "@domain-ui-kit";
import type { DomainRunDescriptor, DomainUiHost, SingleRowFacilityLayoutDraft, TemplateDescriptor } from "@domain-ui-sdk";
import { useEffect, useState } from "react";
import { createEmptyDraft } from "./config/defaults";
import { ExecutionProgress } from "./components/execution/ExecutionProgress";
import { DefinitionImportModal } from "./components/home/DefinitionImportModal";
import { RunsPage } from "./components/home/RunsPage";
import { SrflHome } from "./components/home/SrflHome";
import { ResultSummary } from "./components/results/ResultSummary";
import { ExperimentWizard } from "./components/wizard/ExperimentWizard";
import { useSrflEditor } from "./hooks/useSrflEditor";
import { useSrflExecution } from "./hooks/useSrflExecution";
import { DraftOriginKind, SrflScreenMode } from "./model/editor-state.types";
import { fromScientificDraft, isSrflDefinition } from "./model/mappers";
import "./styles/srfl.css";

const NAVIGATION: readonly SidebarItem<SrflScreenMode>[] = [
  { value: SrflScreenMode.Home, label: "Inicio", icon: "⌂" },
  { value: SrflScreenMode.Editor, label: "Nuevo experimento", icon: "＋" },
  { value: SrflScreenMode.Runs, label: "Ejecuciones", icon: "◷" },
];

export function SingleRowFacilityLayoutScreen({ host }: { host: DomainUiHost }) {
  const editor = useSrflEditor();
  const execution = useSrflExecution(host);
  const [mode, setMode] = useState(SrflScreenMode.Home);
  const [templates, setTemplates] = useState<readonly TemplateDescriptor[]>([]);
  const [runs, setRuns] = useState<DomainRunDescriptor[]>([]);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<(() => void) | null>(null);
  const [homeError, setHomeError] = useState<string | null>(null);
  const [templateBusy, setTemplateBusy] = useState(false);
  const refreshTemplates = async () => {
    try { setTemplates((await host.listTemplates()).filter((item) => item.domain_id === "single-row-facility-layout" && item.domain_version === "1.0.0")); }
    catch (reason) { setHomeError(String(reason)); }
  };
  const refreshRuns = async () => { try { const items = await host.listDomainRuns(); setRuns((items as DomainRunDescriptor[]).filter((item) => item.domain.id === "single-row-facility-layout" && item.domain.version === "1.0.0").sort((left, right) => right.updated_at.localeCompare(left.updated_at))); } catch (reason) { setHomeError(String(reason)); } };

  useEffect(() => {
    void refreshTemplates();
    void refreshRuns();
  }, [host]);
  useEffect(() => { if (execution.result !== null) { setMode(SrflScreenMode.Results); void refreshRuns(); } }, [execution.result]);

  const navigateSafely = (action: () => void) => { if (editor.dirty && mode === SrflScreenMode.Editor) setPendingNavigation(() => action); else action(); };
  const openDraft = (draft: ReturnType<typeof createEmptyDraft>) => { void host.attachments?.discardStaged(); editor.open(draft); setMode(SrflScreenMode.Editor); setHomeError(null); };
  const newDraft = () => navigateSafely(() => openDraft(createEmptyDraft()));
  const importDefinition = async (value: unknown, kind: DraftOriginKind, label: string) => {
    if (!isSrflDefinition(value)) throw new Error("La definición no pertenece al dominio single-row-facility-layout.");
    if ((value as { schema_version?: unknown }).schema_version !== "1.0.0") throw new Error("La definición no pertenece a SRFL 1.0.0.");
    const checked = await host.validateStudy(value);
    openDraft(fromScientificDraft(checked.draft, kind, label));
    setPasteOpen(false);
  };
  const loadTemplate = async (template: TemplateDescriptor) => {
    try { const value = await host.loadTemplate<SingleRowFacilityLayoutDraft>(template.template_id); navigateSafely(() => openDraft(fromScientificDraft(value, DraftOriginKind.Template, `Plantilla ${template.name}`))); }
    catch (reason) { setHomeError(String(reason)); }
  };
  const openFile = async () => { try { const value = await host.openDefinitionFile(); if (value !== null) await importDefinition(value, DraftOriginKind.ImportedFile, "Definición importada"); } catch (reason) { setHomeError(String(reason)); } };
  const run = (draft: SingleRowFacilityLayoutDraft, saveAsTemplate: boolean) => { void execution.start(draft, saveAsTemplate).then((started) => { if (started) { setMode(SrflScreenMode.Execution); if (saveAsTemplate) void refreshTemplates(); } }); };
  const resume = async (runId: string) => { const started = await execution.resume(runId); if (started) setMode(SrflScreenMode.Execution); };
  const openRun = async (run: DomainRunDescriptor) => { setHomeError(null); const opened = await execution.openRun(run.domain_run_id, run.status); if (opened.opened) setMode(opened.result ? SrflScreenMode.Results : SrflScreenMode.Execution); else if ("error" in opened) setHomeError(opened.error ?? "No se pudo abrir la ejecución."); };
  const deleteRun = async (runId: string) => { setHomeError(null); await host.deleteDomainRun(runId); setRuns((items) => items.filter((item) => item.domain_run_id !== runId)); await Promise.all([refreshRuns(), refreshTemplates()]); };
  const currentExperimentId = execution.result?.execution?.domain_experiment_id ?? (execution.state.domainRunId === null ? null : runs.find((item) => item.domain_run_id === execution.state.domainRunId)?.domain_experiment_id ?? null);
  const templateEnabled = currentExperimentId !== null && templates.some((item) => item.domain_experiment_id === currentExperimentId);
  const changeRunTemplate = async (enabled: boolean) => {
    const runId = execution.result?.execution.domain_run_id ?? execution.state.domainRunId;
    if (runId === null) return;
    setTemplateBusy(true); setHomeError(null);
    try { await host.setRunTemplate(runId, enabled); await refreshTemplates(); }
    catch (reason) { setHomeError(String(reason)); }
    finally { setTemplateBusy(false); }
  };
  const selectNavigation = (next: SrflScreenMode) => { if (next === SrflScreenMode.Editor) { newDraft(); return; } navigateSafely(() => { setMode(next); if (next === SrflScreenMode.Runs) void refreshRuns(); }); };

  return <div className="srfl-app"><AppSidebar title="Tesis Project" subtitle="Diseño de instalaciones" items={NAVIGATION} active={mode} onSelect={selectNavigation} footer={<span>SRFL 1.0.0 · protocolo 1.2</span>} /><div className="srfl-content">
    {mode === SrflScreenMode.Home && <><SrflHome templates={templates} onNew={newDraft} onTemplate={loadTemplate} onOpenFile={() => void openFile()} onPaste={() => setPasteOpen(true)} />{homeError !== null && <div className="srfl-toast" role="alert">{homeError}</div>}</>}
    {mode === SrflScreenMode.Editor && editor.draft !== null && <ExperimentWizard host={host} draft={editor.draft} revision={editor.revision} onChange={editor.update} onExit={() => navigateSafely(() => setMode(SrflScreenMode.Home))} onExecute={run} />}
    {mode === SrflScreenMode.Runs && <RunsPage runs={runs} onOpen={openRun} onResume={resume} onDelete={deleteRun} templateExperimentIds={templates.flatMap((item) => item.domain_experiment_id === undefined ? [] : [item.domain_experiment_id])} />}
    {mode === SrflScreenMode.Execution && <ExecutionProgress state={execution.state} cancellationDelayed={execution.cancellationDelayed} onCancel={() => void execution.cancel()} onResume={() => execution.state.domainRunId !== null ? resume(execution.state.domainRunId) : undefined} onHome={() => setMode(SrflScreenMode.Home)} template={templateEnabled} templateBusy={templateBusy} onTemplateChange={currentExperimentId === null ? undefined : (enabled) => void changeRunTemplate(enabled)} />}
    {mode === SrflScreenMode.Results && execution.result !== null && <ResultSummary service={host.attachments} result={execution.result} onHome={() => setMode(SrflScreenMode.Home)} template={templateEnabled} templateBusy={templateBusy} onTemplateChange={(enabled) => void changeRunTemplate(enabled)} />}
    {mode !== SrflScreenMode.Home && homeError !== null && <div className="srfl-toast" role="alert">{homeError}</div>}
  </div>{pasteOpen && <DefinitionImportModal onClose={() => setPasteOpen(false)} onImport={(value) => importDefinition(value, DraftOriginKind.PastedJson, "JSON pegado")} />}{pendingNavigation !== null && <Modal title="Descartar cambios sin preparar" onClose={() => setPendingNavigation(null)} actions={<><Button variant={ButtonVariant.Secondary} onClick={() => setPendingNavigation(null)}>Seguir editando</Button><Button variant={ButtonVariant.Danger} onClick={() => { const action = pendingNavigation; setPendingNavigation(null); editor.clear(); void host.attachments?.discardStaged(); action(); }}>Descartar y continuar</Button></>}><p>El borrador vive sólo en memoria y estos cambios no podrán recuperarse.</p></Modal>}</div>;
}
