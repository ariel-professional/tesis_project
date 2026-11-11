import { StatusBadge } from "@domain-ui-kit";
import type { DomainRunDescriptor } from "@domain-ui-sdk";
import { ExecutionLifecycle } from "../model/execution-state.types";

type RunStatus = DomainRunDescriptor["status"] | ExecutionLifecycle;

const PRESENTATION: Record<RunStatus, { label: string; tone: "neutral" | "success" | "warning" | "danger" | "info" }> = {
  created: { label: "Creada", tone: "neutral" },
  running: { label: "En curso", tone: "info" },
  cancelling: { label: "Cancelando", tone: "warning" },
  completed: { label: "Completada", tone: "success" },
  cancelled: { label: "Cancelada", tone: "warning" },
  failed: { label: "Fallida", tone: "danger" },
  interrupted: { label: "Interrumpida", tone: "warning" },
};

export function RunStatusChip({ status }: { status: RunStatus }) {
  const presentation = PRESENTATION[status];
  return <StatusBadge tone={presentation.tone}>{presentation.label}</StatusBadge>;
}
