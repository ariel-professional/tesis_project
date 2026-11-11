import { ConfigurationKind, type ConfigurationOptionDefinition, type ConfigurationSectionDefinition } from "@domain-ui-kit";
import type { SrflEditorDraft } from "../model/editor-draft.types";

type IntegerLimitName = keyof SrflEditorDraft["execution"]["integer_limits"];

function integerLimit(name: IntegerLimitName, title: string, description: string, min = 1): ConfigurationOptionDefinition<SrflEditorDraft> {
  return {
    kind: ConfigurationKind.Integer,
    fieldName: `execution.integer_limits.${name}`,
    title, description, min,
    getValue: (draft) => draft.execution.integer_limits[name],
    setValue: (draft, value) => ({ ...draft, execution: { ...draft.execution, integer_limits: { ...draft.execution.integer_limits, [name]: value } } }),
  };
}

export const SRFL_CONFIGURATION_SECTIONS: readonly ConfigurationSectionDefinition<SrflEditorDraft>[] = [
  {
    id: "persistence", title: "Persistencia y reporte", options: [
      { kind: ConfigurationKind.Boolean, fieldName: "execution.persistence.persist_events", title: "Persistir eventos", description: "Conserva los eventos detallados de ejecución en el workspace.", getValue: (draft) => draft.execution.persistence.persist_events, setValue: (draft, value) => ({ ...draft, execution: { ...draft.execution, persistence: { ...draft.execution.persistence, persist_events: value } } }) },
      { kind: ConfigurationKind.Select, fieldName: "execution.persistence.policy", title: "Política de persistencia", description: "Selecciona persistencia normal o información adicional de depuración.", options: [{ value: "normal", label: "Normal" }, { value: "debug", label: "Depuración" }], getValue: (draft) => draft.execution.persistence.policy, setValue: (draft, value) => ({ ...draft, execution: { ...draft.execution, persistence: { ...draft.execution.persistence, policy: value as "normal" | "debug" } } }) },
      { kind: ConfigurationKind.Select, fieldName: "reporting.invalid_combinations", title: "Combinaciones inválidas", description: "Define si el resultado incluye un resumen o el detalle completo.", options: [{ value: "summary", label: "Resumen" }, { value: "full", label: "Detalle completo" }], getValue: (draft) => draft.reporting.invalid_combinations, setValue: (draft, value) => ({ ...draft, reporting: { invalid_combinations: value as "summary" | "full" } }) },
    ],
  },
  {
    id: "problem-limits", title: "Tamaño del problema", description: "Límites que controlan el alcance científico del experimento.",
    options: [
      integerLimit("max_n", "Máximo de estaciones", "Cantidad máxima de estaciones admitida por el experimento."),
      integerLimit("reference_max_n", "Máximo del método de referencia", "Tamaño máximo permitido para la verificación por fuerza bruta."),
      integerLimit("exact_timeout_ms", "Timeout exacto", "Tiempo máximo en milisegundos para el método exacto."),
      integerLimit("reference_timeout_ms", "Timeout de referencia", "Tiempo máximo en milisegundos para el método de referencia."),
    ],
  },
  {
    id: "transport-limits", title: "Control y mensajes", description: "Límites operativos usados por workers, eventos y cancelación.",
    options: [
      integerLimit("cancellation_grace_ms", "Espera de cancelación", "Tiempo de gracia para que una cancelación cooperativa termine.", 0),
      integerLimit("control_connect_timeout_ms", "Conexión de control", "Espera máxima para conectar con el canal de control."),
      integerLimit("control_response_timeout_ms", "Respuesta de control", "Espera máxima de una respuesta del canal de control."),
      integerLimit("control_max_message_bytes", "Mensaje de control", "Tamaño máximo en bytes de un mensaje de control."),
      integerLimit("event_max_payload_bytes", "Payload de evento", "Tamaño máximo en bytes del contenido de un evento."),
      integerLimit("worker_max_message_bytes", "Mensaje de worker", "Tamaño máximo en bytes intercambiado con un worker."),
      integerLimit("input_max_bytes", "Entrada", "Tamaño máximo en bytes de la entrada científica."),
    ],
  },
  {
    id: "logs", title: "Logs", options: [
      integerLimit("runner_log_max_bytes", "Tamaño de log", "Tamaño máximo de cada archivo de log del runner."),
      integerLimit("runner_log_backup_count", "Copias de log", "Cantidad de archivos rotados que se conservan.", 0),
    ],
  },
  {
    id: "methods", title: "Métodos", options: [
      { kind: ConfigurationKind.Readonly, fieldName: "execution.counting_convention", title: "Convención de conteo", description: "Los caminos inversos se consideran la misma disposición.", getValue: (draft) => draft.execution.counting_convention },
      { kind: ConfigurationKind.Readonly, fieldName: "execution.methods.exact.engine", title: "Motor exacto", description: "Motor configurado para el cálculo exacto.", getValue: (draft) => draft.execution.methods.exact.engine },
      { kind: ConfigurationKind.Readonly, fieldName: "execution.methods.reference.engine", title: "Motor de referencia", description: "Motor usado para la comprobación independiente.", getValue: (draft) => draft.execution.methods.reference.engine },
    ],
  },
];
