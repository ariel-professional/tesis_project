import type { FileAttachment, LinkAttachment } from "../../src/generated/single-row-facility-layout";
import type { SingleRowFacilityLayoutConfig } from "../../src/generated/single-row-facility-layout";
import type { SingleRowFacilityLayoutConfigV2 } from "../../src/generated/single-row-facility-layout-v2";

export type { FileAttachment, LinkAttachment };
export type Attachment = FileAttachment | LinkAttachment;
export type EvidenceValue = { description: string; attachments: Attachment[] };
export type EvidenceUpdate = (current: EvidenceValue) => EvidenceValue;

export interface AttachmentService {
  stage(file: File, signal: AbortSignal, onProgress: (fraction: number) => void): Promise<FileAttachment>;
  readRange(file: FileAttachment, offset: number, length: number): Promise<Uint8Array>;
  openLink(url: string): Promise<void>;
  documentation(experimentId: string): Promise<SingleRowFacilityLayoutConfig | SingleRowFacilityLayoutConfigV2>;
  discardStaged(): Promise<void>;
}
