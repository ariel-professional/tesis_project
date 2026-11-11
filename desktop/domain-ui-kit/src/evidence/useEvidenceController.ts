import { useEffect, useRef, useState } from "react";
import type { Attachment, AttachmentService, EvidenceUpdate, FileAttachment } from "@domain-ui-sdk";

export const attachmentKey = (item: Attachment): string => item.kind === "file" ? `file:${item.sha256}` : `link:${item.url}`;
export function useEvidenceController(service: AttachmentService | undefined, onChange?: (update: EvidenceUpdate) => void, onBusy?: (delta: number) => void) {
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewer, setViewer] = useState<FileAttachment | null>(null);
  const [opening, setOpening] = useState(false);
  const active = useRef<AbortController | null>(null);
  const callbacks = useRef({ onChange, onBusy });
  callbacks.current = { onChange, onBusy };
  useEffect(() => () => { active.current?.abort(); }, []);

  const upload = async (files: readonly File[]) => {
    if (!service || !callbacks.current.onChange || active.current) return;
    const controller = new AbortController();
    active.current = controller;
    setProgress(0);
    callbacks.current.onBusy?.(1);
    setError(null);
    try {
      for (const [index, file] of files.entries()) {
        controller.signal.throwIfAborted();
        const attachment = await service.stage(file, controller.signal, (fraction) => setProgress((index + fraction) / files.length));
        controller.signal.throwIfAborted();
        callbacks.current.onChange?.((current) => ({ ...current, attachments: [
          ...current.attachments.filter((item) => attachmentKey(item) !== attachmentKey(attachment)), attachment,
        ] }));
      }
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      active.current = null;
      callbacks.current.onBusy?.(-1);
      if (!controller.signal.aborted) setProgress(null);
    }
  };
  const open = async (attachment: Attachment) => {
    setError(null);
    if (!service) { setError("El servicio de adjuntos no está disponible."); return; }
    if (attachment.kind === "file") setViewer(attachment);
    else {
      setOpening(true);
      try { await service.openLink(attachment.url); }
      catch (reason) { setError(String(reason)); }
      finally { setOpening(false); }
    }
  };
  return { upload, open, opening, progress, error, setError, viewer, closeViewer: () => setViewer(null), cancel: () => { active.current?.abort(); setProgress(null); } };
}
