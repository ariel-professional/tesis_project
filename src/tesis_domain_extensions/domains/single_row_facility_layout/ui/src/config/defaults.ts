import { DraftOriginKind } from "../model/editor-state.types";
import type { SrflEditorDraft } from "../model/editor-draft.types";
import { newStudyIdentifier, nextClientKey } from "../model/identifiers";

export function createEmptyDraft(version: "2.0.0" | "2.1.0" = "2.0.0"): SrflEditorDraft {
  return {
    schemaVersion: version,
    domain: { id: "single-row-facility-layout", version },
    origin: { kind: DraftOriginKind.Empty, label: "Experimento nuevo" },
    study: {
      id: newStudyIdentifier(),
      title: "Nuevo experimento",
      description: "",
      stations: [],
      stationDisplayOrder: [],
      components: [],
      designs: [{ clientKey: nextClientKey("design"), id: "diseno-1", idManuallyEdited: false, title: "Diseño 1", baseComponentIds: [] }],
    },
    execution: {
      counting_convention: "undirected_paths_reverse_identified",
      integer_limits: {
        cancellation_grace_ms: 1000, control_connect_timeout_ms: 1000,
        control_max_message_bytes: 16384, control_response_timeout_ms: 1000,
        event_max_payload_bytes: 65536, exact_timeout_ms: 30000,
        input_max_bytes: 1048576, max_n: 100, reference_max_n: 6,
        reference_timeout_ms: 30000, runner_log_backup_count: 3,
        runner_log_max_bytes: 5242880, worker_max_message_bytes: 65536,
      },
      methods: { exact: { engine: "auto" }, reference: { engine: "bruteforce_python_v1" } },
      persistence: { persist_events: false, policy: "normal" },
      ...(version === "2.1.0" ? { mode: "standard" as const } : {}),
    },
    decisionModel: { selectedObjectives: [{ id: "retained-compatible-layouts", version: "1" }], retainedCompatibleLayouts: true, relCloseness: null, adjacencyMatrices: [], undesiredPrescribedAdjacencies: [] },
    reporting: { invalid_combinations: "summary" },
  };
}
