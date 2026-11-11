import {
  Button,
  ButtonVariant,
  ActionButton,
  ActionIconButton,
  Card,
  EmptyState,
  Modal,
  PageHeader,
} from "@domain-ui-kit";
import type { DomainRunDescriptor } from "@domain-ui-sdk";
import { useMemo, useState } from "react";
import { RunStatusChip } from "../RunStatusChip";

export function RunsPage({
  runs,
  onOpen,
  onResume,
  onDelete,
  templateExperimentIds,
}: {
  runs: readonly DomainRunDescriptor[];
  onOpen: (run: DomainRunDescriptor) => Promise<void>;
  onResume: (id: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  templateExperimentIds: readonly string[];
}) {
  const [pending, setPending] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [target, setTarget] = useState<DomainRunDescriptor | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const normalizedQuery = query.trim().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();
  const filteredRuns = useMemo(() => {
    if (!normalizedQuery) return runs;
    const compact = normalizedQuery.replaceAll("-", "");
    return runs.filter((run) => [run.display_name, run.domain_run_id, run.domain_experiment_id]
      .filter((field): field is string => typeof field === "string")
      .some((field) => {
        const normalized = field.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();
        return normalized.includes(normalizedQuery) || normalized.replaceAll("-", "").includes(compact);
      }));
  }, [runs, normalizedQuery]);
  const perform = async (key: string, action: () => Promise<void>) => {
    if (pending !== null) return;
    setPending(key);
    try {
      await action();
    } finally {
      setPending(null);
    }
  };
  return (
    <main className="srfl-page">
      <PageHeader
        title="Ejecuciones"
        description="Consultá el resultado o los detalles disponibles de cualquier ejecución."
      />
      {runs.length === 0 ? (
        <EmptyState
          title="Todavía no hay ejecuciones"
          description="Prepará tu primer experimento para comenzar a construir evidencia."
        />
      ) : (
        <>
        <label className="srfl-run-search">Buscar ejecuciones<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nombre o ID de ejecución / experimento" /></label>
        {filteredRuns.length === 0 ? <EmptyState title="No hay coincidencias" description="Probá con otro nombre o identificador." /> : <div className="srfl-run-list">
          {filteredRuns.map((run) => {
            const opening = pending === `open:${run.domain_run_id}`;
            const resuming = pending === `resume:${run.domain_run_id}`;
            const deleting = pending === `delete:${run.domain_run_id}`;
            const canResume =
              run.status !== "completed" && run.status !== "running";
            return (
              <Card key={run.domain_run_id}>
                <div>
                  <RunStatusChip status={run.status} />
                  <h3>{run.display_name}</h3>
                  <p>
                    ID: <code title={run.domain_run_id}>{run.domain_run_id}</code>
                  </p>
                  <p>Actualizado {new Date(run.updated_at).toLocaleString("es-AR")}</p>
                </div>
                <div className="srfl-run-actions">
                  {run.status === "completed" ? (
                    <ActionButton
                      action="view-results"
                      label={opening ? "Abriendo resultados…" : "Ver resultado"}
                      variant={ButtonVariant.Secondary}
                      loading={opening}
                      disabled={pending !== null}
                      onClick={() => void perform(`open:${run.domain_run_id}`, () => onOpen(run))}
                    />
                  ) : (
                    <ActionIconButton
                      action="view-details"
                      label={opening ? "Abriendo…" : "Ver detalles"}
                      loading={opening}
                      disabled={pending !== null}
                      aria-busy={opening}
                      onClick={() => void perform(`open:${run.domain_run_id}`, () => onOpen(run))}
                    />
                  )}
                  {canResume && (
                    <ActionIconButton
                      action="resume"
                      label={resuming ? "Reanudando…" : "Reanudar"}
                      loading={resuming}
                      disabled={pending !== null}
                      aria-busy={resuming}
                      onClick={() =>
                        void perform(`resume:${run.domain_run_id}`, () =>
                          onResume(run.domain_run_id),
                        )
                      }
                    />
                  )}
                  <ActionIconButton action="delete" label="Eliminar experimento" className="srfl-run-action srfl-run-action--danger" disabled={pending !== null || run.status === "running"} aria-busy={deleting} onClick={() => { setDeleteError(null); setTarget(run); }} />
                </div>
              </Card>
            );
          })}
        </div>}
        {deleteError !== null && <p role="alert">{deleteError}</p>}
        {target !== null && <Modal title="Eliminar experimento" onClose={() => { if (pending === null) setTarget(null); }} actions={<><Button variant={ButtonVariant.Secondary} disabled={pending !== null} onClick={() => setTarget(null)}>Cancelar</Button><ActionButton action="delete" label={pending === `delete:${target.domain_run_id}` ? "Eliminando ejecución y resultados…" : "Eliminar ejecución y resultados"} loading={pending === `delete:${target.domain_run_id}`} variant={ButtonVariant.Danger} disabled={pending !== null} onClick={() => { const id = target.domain_run_id; setDeleteError(null); void perform(`delete:${id}`, async () => { try { await onDelete(id); setTarget(null); } catch (reason) { setDeleteError(String(reason)); } }); }} /></>}>
          <p><strong>{target.display_name}</strong></p>
          <p>ID de ejecución: <code>{target.domain_run_id}</code></p>
          <p>Se perderán los resultados y las posibilidades de reanudar esta ejecución.</p>
          {target.domain_experiment_id !== undefined && templateExperimentIds.includes(target.domain_experiment_id) && <p>La plantilla guardada permanecerá disponible.</p>}
        </Modal>}
        </>
      )}
    </main>
  );
}
