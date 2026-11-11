import { lazy, Suspense, useEffect, useId, useState } from "react";
import type { AttachmentService, EvidenceUpdate, EvidenceValue } from "@domain-ui-sdk";
import { Button, ButtonVariant } from "../components/Button";
import { ActionButton } from "../components/ActionButton";
import { TextAreaField, TextField } from "../components/FormField";
import { attachmentKey, useEvidenceController } from "./useEvidenceController";
import "./evidence.css";

const Viewer = lazy(() => import("./AttachmentViewerModal"));
export function EvidenceEditor({ value, onChange, service, onBusy, label = "Descripción", readOnly = false }: {
  value: EvidenceValue; onChange?: (update: EvidenceUpdate) => void; service?: AttachmentService;
  onBusy?: (delta: number) => void; label?: string; readOnly?: boolean;
}) {
  const [tab, setTab] = useState<"file" | "link">("file");
  const [url, setUrl] = useState("");
  const [linkLabel, setLinkLabel] = useState("");
  const id = useId();
  const control = useEvidenceController(service, onChange, onBusy);
  const [unavailable, setUnavailable] = useState<Record<string, string>>({});
  const fileKeys = value.attachments.filter((item) => item.kind === "file").map(attachmentKey).join("|");
  useEffect(() => {
    let current = true;
    setUnavailable({});
    for (const attachment of value.attachments) {
      if (attachment.kind === "file" && service) void service.readRange(attachment, 0, 0).catch((reason: unknown) => {
        if (current) setUnavailable((previous) => ({ ...previous, [attachmentKey(attachment)]: String(reason) }));
      });
    }
    return () => { current = false; };
  }, [fileKeys, service]);
  const addLink = () => {
    try {
      const parsed = new URL(url.trim());
      if (!["http:", "https:"].includes(parsed.protocol) || !parsed.hostname || /\s/.test(url.trim())) throw new Error();
      const attachment = { kind: "link" as const, url: url.trim(), label: linkLabel.trim() || null };
      onChange?.((current) => ({ ...current, attachments: [...current.attachments.filter((item) => attachmentKey(item) !== attachmentKey(attachment)), attachment] }));
      setUrl(""); setLinkLabel(""); control.setError(null);
    } catch { control.setError("Ingresá una URL HTTP o HTTPS completa."); }
  };
  return <section className="ui-evidence" aria-label={label}>
    {readOnly ? value.description && <p className="ui-evidence__description">{value.description}</p> : <TextAreaField label={label} value={value.description} onChange={(event) => { const description = event.target.value; onChange?.((current) => ({ ...current, description })); }} />}
    {!readOnly && <>
      <div className="ui-evidence__tabs" role="tablist" aria-label="Tipo de antecedente">
        {(["file", "link"] as const).map((kind) => <button type="button" key={kind} role="tab" id={`${id}-${kind}`} aria-controls={`${id}-panel`} aria-selected={tab === kind} tabIndex={tab === kind ? 0 : -1} onClick={() => setTab(kind)} onKeyDown={(event) => {
          if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
            event.preventDefault(); const next = kind === "file" ? "link" : "file"; setTab(next); document.getElementById(`${id}-${next}`)?.focus();
          }
        }}>{kind === "file" ? "Imagen / Plano / PDF" : "URL / Link"}</button>)}
      </div>
      <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${tab}`}>
        {tab === "file" ? <div className="ui-evidence__drop" onDragOver={(event) => { event.preventDefault(); }} onDrop={(event) => { event.preventDefault(); void control.upload(Array.from(event.dataTransfer.files)); }}>
          <span>Arrastrá imágenes, planos o documentos PDF</span>
          <label className="ui-evidence__select">Seleccionar archivos<input type="file" aria-label="Seleccionar archivos" multiple accept=".png,.jpg,.jpeg,.webp,.pdf" disabled={!service || control.progress !== null} onChange={(event) => { void control.upload(Array.from(event.target.files ?? [])); event.target.value = ""; }} /></label>
          <small>PNG, JPG, WebP y PDF · sin límite de tamaño impuesto</small>
        </div> : <div className="ui-evidence__link"><TextField label="URL" value={url} onChange={(event) => setUrl(event.target.value)} /><TextField label="Etiqueta (opcional)" value={linkLabel} onChange={(event) => setLinkLabel(event.target.value)} /><Button variant={ButtonVariant.Secondary} onClick={addLink}>Agregar enlace</Button></div>}
      </div>
    </>}
    {control.progress !== null && <div role="status">Copiando… {Math.round(control.progress * 100)} % <Button variant={ButtonVariant.Ghost} onClick={control.cancel}>Cancelar carga</Button></div>}
    <ul className="ui-evidence__list">{value.attachments.map((attachment) => <li key={attachmentKey(attachment)}>
      <div><strong>{attachment.kind === "file" ? attachment.name : attachment.label || attachment.url}</strong><small>{attachment.kind === "file" ? `${attachment.media_type} · ${new Intl.NumberFormat("es").format(attachment.size_bytes)} bytes` : attachment.url}</small></div>
      {unavailable[attachmentKey(attachment)] && <small role="alert">Adjunto pendiente o no disponible. {readOnly ? unavailable[attachmentKey(attachment)] : "Volvé a adjuntar el archivo original o quitá esta referencia."}</small>}
      <div className="ui-evidence__actions"><ActionButton action="open" label={control.opening && attachment.kind === "link" ? "Abriendo enlace…" : attachment.kind === "file" ? "Ver adjunto" : "Abrir enlace"} loading={control.opening && attachment.kind === "link"} variant={ButtonVariant.Ghost} onClick={() => void control.open(attachment)} />{!readOnly && <Button variant={ButtonVariant.Ghost} onClick={() => onChange?.((current) => ({ ...current, attachments: current.attachments.filter((item) => attachmentKey(item) !== attachmentKey(attachment)) }))}>Quitar</Button>}</div>
    </li>)}</ul>
    {readOnly && !value.description && value.attachments.length === 0 && <small>Sin antecedentes documentados.</small>}
    {control.error && <p role="alert">{control.error}</p>}
    {control.viewer && service && <Suspense fallback={<p role="status">Abriendo visor…</p>}><Viewer file={control.viewer} service={service} onClose={control.closeViewer} /></Suspense>}
  </section>;
}
