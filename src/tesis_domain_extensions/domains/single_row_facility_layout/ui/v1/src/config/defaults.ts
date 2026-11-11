import { DraftOriginKind } from "../model/editor-state.types";
import type { SrflEditorDraft } from "../model/editor-draft.types";
import { newStudyIdentifier, nextClientKey } from "../model/identifiers";

export function createEmptyDraft(): SrflEditorDraft {
  return {
    schemaVersion: "1.0.0",
    domain: { id: "single-row-facility-layout", version: "1.0.0" },
    origin: { kind: DraftOriginKind.Empty, label: "Experimento nuevo" },
    study: {
      id: newStudyIdentifier(),
      title: "Nuevo experimento",
      description: "",
      stations: [],
      components: [],
      designs: [{ clientKey: nextClientKey("design"), id: "diseno-1", idManuallyEdited: false, title: "Diseño 1", baseComponentIds: [] }],
    },
    execution: {
      counting_convention: "undirected_paths_reverse_identified",
      integer_limits: {
        cancellation_grace_ms: 1000, control_connect_timeout_ms: 1000,
        control_max_message_bytes: 16384, control_response_timeout_ms: 1000,
        event_max_payload_bytes: 65536, exact_timeout_ms: 30000,
        input_max_bytes: 1048576, max_n: 12, reference_max_n: 10,
        reference_timeout_ms: 30000, runner_log_backup_count: 3,
        runner_log_max_bytes: 5242880, worker_max_message_bytes: 65536,
      },
      methods: { exact: { engine: "auto" }, reference: { engine: "bruteforce_python_v1" } },
      persistence: { persist_events: false, policy: "normal" },
    },
    reporting: { invalid_combinations: "summary" },
  };
}
