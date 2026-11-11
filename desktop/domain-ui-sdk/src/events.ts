import type { GatewayMessage } from "../../src/generated/gateway-message";

// v1 event fixtures remain readable by the renderer test/inspection layer; the
// runtime gateway validates and emits protocol 1.5 and earlier.
type RendererEventWithHistoricalProtocol<T> = T extends { protocol_version: string }
  ? Omit<T, "protocol_version"> & { protocol_version: "1.0" | "1.1" | "1.2" | "1.3" | "1.4" | "1.5" }
  : T;
type HistoricalOperationEvent = {
  protocol_version: "1.0";
  message_type: "event";
  operation_id: string;
  sequence: number;
  event: string;
  data: any;
};
export type DomainOperationEvent = RendererEventWithHistoricalProtocol<Extract<GatewayMessage, { event: string }>> | HistoricalOperationEvent;

export enum BackendConnectionState {
  Connected = "connected",
  Restarting = "restarting",
  Disconnected = "disconnected",
}

export type BackendStateEvent = {
  readonly state: BackendConnectionState;
  readonly interruptedOperationIds: readonly string[];
};
