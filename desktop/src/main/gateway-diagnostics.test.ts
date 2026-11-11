import { expect, test } from "vitest";
import { gatewayExitMessage } from "./gateway-diagnostics";

test("gateway termination reports its signal and detected protocol failure", () => {
  expect(gatewayExitMessage({
    code: null,
    signal: "SIGTERM",
    protocolFailure: "se recibió un frame que no es JSON válido",
  })).toBe(
    "El gateway terminó inesperadamente (señal SIGTERM). Motivo detectado: se recibió un frame que no es JSON válido",
  );
});

test("gateway termination reports a numeric process exit", () => {
  expect(gatewayExitMessage({ code: 74, signal: null, protocolFailure: null })).toBe(
    "El gateway terminó inesperadamente (código 74).",
  );
});
