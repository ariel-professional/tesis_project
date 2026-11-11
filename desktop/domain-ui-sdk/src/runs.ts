export type AcceptedOperation = { readonly operation_id: string; readonly domain_run_id: string };
export type DomainRunDescriptor = {
  readonly domain_run_id: string;
  readonly domain_experiment_id?: string;
  readonly domain: { readonly id: string; readonly version: string };
  readonly display_name: string;
  readonly status: "created" | "running" | "failed" | "cancelled" | "completed";
  readonly updated_at: string;
  readonly created_at?: string;
  readonly generation?: { readonly theoretical_combinations: number | string; readonly valid_selections: number | string };
  readonly active_duration_ms?: number;
  readonly active_started_at?: string | null;
  readonly mode?: "standard" | "high_performance";
};
