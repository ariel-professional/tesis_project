import type { AttachmentService, FileAttachment, SingleRowFacilityLayoutDraft, SingleRowFacilityLayoutDraftV2 } from "@domain-ui-sdk";

const BLOCK_BYTES = 512 * 1024;
const TYPES: Record<string, FileAttachment["media_type"]> = {
  png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", webp: "image/webp", pdf: "application/pdf",
};

function encode(bytes: Uint8Array): string {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 8192) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  }
  return btoa(binary);
}

export class ElectronAttachmentService implements AttachmentService {
  private readonly staged = new Set<string>();

  async stage(file: File, signal: AbortSignal, onProgress: (fraction: number) => void): Promise<FileAttachment> {
    const media = TYPES[file.name.split(".").pop()?.toLowerCase() ?? ""];
    if (!media) throw new Error("Seleccioná PNG, JPG, WebP o PDF.");
    signal.throwIfAborted();
    const started = await window.desktopApi.beginAttachment(file.name, media, file.size);
    const { upload_id: uploadId } = started.result as { upload_id: string };
    this.staged.add(uploadId);
    try {
      for (let offset = 0; offset < file.size; offset += BLOCK_BYTES) {
        signal.throwIfAborted();
        const bytes = new Uint8Array(await file.slice(offset, offset + BLOCK_BYTES).arrayBuffer());
        signal.throwIfAborted();
        await window.desktopApi.appendAttachment(uploadId, offset, encode(bytes));
        onProgress(Math.min(1, (offset + bytes.length) / file.size));
      }
      signal.throwIfAborted();
      const finished = await window.desktopApi.finishAttachment(uploadId);
      signal.throwIfAborted();
      return finished.result as FileAttachment;
    } catch (error) {
      await window.desktopApi.abortAttachment(uploadId).catch(() => undefined);
      this.staged.delete(uploadId);
      throw error;
    }
  }

  async readRange(file: FileAttachment, offset: number, length: number): Promise<Uint8Array> {
    // PDF.js may request several transport blocks in a single range.
    const result = new Uint8Array(Math.max(0, Math.min(length, file.size_bytes - offset)));
    let copied = 0;
    do {
      const reply = await window.desktopApi.readAttachment(file.sha256, offset + copied, Math.min(BLOCK_BYTES, result.length - copied));
      const data = atob((reply.result as { data: string }).data);
      for (let index = 0; index < data.length; index += 1) result[copied + index] = data.charCodeAt(index);
      if (data.length === 0 && copied < result.length) throw new Error("El adjunto está incompleto.");
      copied += data.length;
    } while (copied < result.length);
    return result;
  }

  async openLink(url: string): Promise<void> { await window.desktopApi.openEvidenceLink(url); }
  async documentation(experimentId: string): Promise<SingleRowFacilityLayoutDraft | SingleRowFacilityLayoutDraftV2> {
    return (await window.desktopApi.getStudyDocumentation(experimentId)).result as SingleRowFacilityLayoutDraft | SingleRowFacilityLayoutDraftV2;
  }
  async discardStaged(): Promise<void> {
    const ids = [...this.staged];
    this.staged.clear();
    await Promise.all(ids.map((id) => window.desktopApi.abortAttachment(id).catch(() => undefined)));
  }
}
