export type GatewayExitDetails = {
  code: number | null;
  signal: NodeJS.Signals | null;
  protocolFailure: string | null;
};

export function gatewayExitMessage({ code, signal, protocolFailure }: GatewayExitDetails): string {
  const outcome = code === null
    ? `señal ${signal ?? "desconocida"}`
    : `código ${code}`;
  const reason = protocolFailure === null ? "" : ` Motivo detectado: ${protocolFailure}`;
  return `El gateway terminó inesperadamente (${outcome}).${reason}`;
}
