import { ActionButton, Button, ButtonVariant, Modal } from "@domain-ui-kit";
import { useState } from "react";

export function DefinitionImportModal({ onClose, onImport }: { onClose: () => void; onImport: (value: unknown) => Promise<void> }) {
  const [source, setSource] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (busy) return;
    setBusy(true);
    try { setError(null); await onImport(JSON.parse(source) as unknown); }
    catch (reason) { setError(reason instanceof SyntaxError ? "El contenido no es JSON válido." : String(reason)); }
    finally { setBusy(false); }
  };
  return <Modal title="Pegar definición JSON" onClose={() => { if (!busy) onClose(); }} actions={<><Button variant={ButtonVariant.Secondary} disabled={busy} onClick={onClose}>Cancelar</Button><ActionButton action="validate" label={busy ? "Validando…" : "Validar y crear borrador"} loading={busy} disabled={source.trim() === "" || busy} onClick={() => void submit()} /></>}>
    <label className="ui-field"><span className="ui-field__label">Definición completa</span><span className="ui-field__description">Pegá una configuración SRFL existente. Después de validarla se abrirá como formularios visuales.</span><textarea className="ui-input srfl-json-input" value={source} onChange={(event) => setSource(event.target.value)} disabled={busy} spellCheck={false} /></label>
    {error !== null && <p className="srfl-error" role="alert">{error}</p>}
  </Modal>;
}

