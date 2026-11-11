import { useEffect, useRef, useState } from "react";
import type { AttachmentService, FileAttachment } from "@domain-ui-sdk";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { Modal } from "../components/Modal";
import { Button, ButtonVariant } from "../components/Button";
import { ActionButton } from "../components/ActionButton";

export default function AttachmentViewerModal({ file, service, onClose }: { file: FileAttachment; service: AttachmentService; onClose: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [image, setImage] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [renderingPage, setRenderingPage] = useState(false);
  const canvas = useRef<HTMLCanvasElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const renderTask = useRef<RenderTask | null>(null);
  useEffect(() => {
    let stopped = false;
    let dispose = () => {};
    let imageUrl: string | null = null;
    const load = async () => {
      if (file.media_type === "application/pdf") {
        const lib = await import("pdfjs-dist");
        if (stopped) return;
        const worker = new Worker(new URL("pdfjs-dist/build/pdf.worker.mjs", import.meta.url), { type: "module" });
        const pdfWorker = lib.PDFWorker.create({ port: worker });
        class RangeTransport extends lib.PDFDataRangeTransport {
          requestDataRange(begin: number, end: number): void {
            void service.readRange(file, begin, end - begin).then((data) => { if (!stopped) this.onDataRange(begin, data); }).catch((reason: unknown) => { if (!stopped) setError(String(reason)); });
          }
        }
        const transport = new RangeTransport(file.size_bytes, new Uint8Array(), false);
        const assets = new URL("../pdfjs/", window.location.href);
        const task = lib.getDocument({
          range: transport, worker: pdfWorker, disableAutoFetch: true, disableStream: true,
          cMapUrl: new URL("cmaps/", assets).href, cMapPacked: true,
          standardFontDataUrl: new URL("standard_fonts/", assets).href,
          wasmUrl: new URL("wasm/", assets).href, useWorkerFetch: false,
        });
        dispose = () => { transport.abort(); void task.destroy(); worker.terminate(); };
        const document = await task.promise;
        if (!stopped) setPdf(document);
      } else {
        let offset = 0;
        const stream = new ReadableStream<Uint8Array>({
          async pull(controller) {
            if (stopped || offset >= file.size_bytes) { controller.close(); return; }
            const bytes = await service.readRange(file, offset, Math.min(512 * 1024, file.size_bytes - offset));
            offset += bytes.length;
            controller.enqueue(bytes);
          },
        });
        const blob = await new Response(stream, { headers: { "Content-Type": file.media_type } }).blob();
        if (stopped) return;
        imageUrl = URL.createObjectURL(blob);
        setImage(imageUrl);
      }
    };
    void load().catch((reason: unknown) => { if (!stopped) setError(String(reason)); });
    return () => { stopped = true; renderTask.current?.cancel(); dispose(); if (imageUrl) URL.revokeObjectURL(imageUrl); };
  }, [file, service]);
  useEffect(() => {
    if (!pdf) return;
    let stopped = false;
    const paint = async () => {
      setRenderingPage(true);
      try {
        renderTask.current?.cancel();
        await renderTask.current?.promise.catch(() => undefined);
        const source = await pdf.getPage(page);
        if (stopped || !canvas.current) return;
        const width = Math.max(200, (container.current?.clientWidth ?? 800) - 32);
        const scale = width / source.getViewport({ scale: 1 }).width * zoom;
        const viewport = source.getViewport({ scale });
        const target = canvas.current;
        target.width = viewport.width; target.height = viewport.height;
        renderTask.current = source.render({ canvas: target, viewport });
        await renderTask.current.promise;
      } finally {
        if (!stopped) setRenderingPage(false);
      }
    };
    void paint().catch((reason: unknown) => { if (!stopped) setError(String(reason)); });
    return () => { stopped = true; renderTask.current?.cancel(); };
  }, [pdf, page, zoom]);
  return <Modal title={file.name} onClose={onClose} className="ui-attachment-modal">
    <div className="ui-evidence__actions">
      {pdf && <><ActionButton action="previous" label="Página anterior" loading={renderingPage && page > 1} variant={ButtonVariant.Secondary} disabled={page <= 1 || renderingPage} onClick={() => setPage(page - 1)} /><span>Página {page} de {pdf.numPages}</span><ActionButton action="next" label="Página siguiente" loading={renderingPage && page < pdf.numPages} variant={ButtonVariant.Secondary} disabled={page >= pdf.numPages || renderingPage} onClick={() => setPage(page + 1)} /></>}
      <Button variant={ButtonVariant.Secondary} onClick={() => setZoom((value) => Math.max(.25, value / 1.25))}>−</Button><span>{Math.round(zoom * 100)} %</span><Button variant={ButtonVariant.Secondary} onClick={() => setZoom((value) => Math.min(5, value * 1.25))}>+</Button><Button variant={ButtonVariant.Ghost} onClick={() => setZoom(1)}>Ajustar al ancho</Button>
    </div>
    {error ? <p role="alert">No se pudo visualizar el adjunto: {error}</p> : !pdf && !image && <p role="status">Cargando adjunto…</p>}
    <div className="ui-attachment-viewport" ref={container}>{pdf && <canvas ref={canvas} aria-label={`Página ${page}`} />}{image && <img src={image} alt={file.name} style={{ width: `${zoom * 100}%`, maxWidth: "none" }} onError={() => setError("El archivo de imagen no se puede decodificar.")} />}</div>
  </Modal>;
}
