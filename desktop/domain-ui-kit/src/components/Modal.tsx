import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Button, ButtonVariant, IconButton } from "./Button";

export function Modal({ title, children, onClose, actions, className = "", backdropClassName = "" }: { title: string; children: ReactNode; onClose: () => void; actions?: ReactNode; className?: string; backdropClassName?: string }) {
  const panel = useRef<HTMLElement>(null);
  const close = useRef(onClose); close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const keyboard = (event: KeyboardEvent) => {
      if (document.querySelectorAll('[role="dialog"]')[document.querySelectorAll('[role="dialog"]').length - 1] !== panel.current) return;
      if (event.key === "Escape") { event.preventDefault(); event.stopImmediatePropagation(); close.current(); }
      if (event.key === "Tab") {
        const elements = [...(panel.current?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), textarea, select, a[href], [tabindex="0"]') ?? [])].filter((element) => element.getClientRects().length > 0);
        const first = elements[0]; const last = elements[elements.length - 1];
        if (!first) { event.preventDefault(); return; }
        if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", keyboard);
    return () => { document.removeEventListener("keydown", keyboard); previous?.focus(); };
  }, []);
  return createPortal(<div className={`ui-modal-backdrop ${backdropClassName}`.trim()} role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={panel} tabIndex={-1} className={`ui-modal ${className}`} role="dialog" aria-modal="true" aria-label={title}>
      <header><h2>{title}</h2><IconButton label="Cerrar" onClick={onClose}><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" /></svg></IconButton></header>
      <div className="ui-modal__body">{children}</div>
      {actions !== undefined && <footer>{actions}</footer>}
    </section>
  </div>, document.body);
}

export function DependencyConfirmationModal({ title, dependencies, onConfirm, onClose }: { title: string; dependencies: readonly string[]; onConfirm: () => void; onClose: () => void }) {
  return <Modal title={title} onClose={onClose} actions={<><Button variant={ButtonVariant.Secondary} onClick={onClose}>Conservar</Button><Button variant={ButtonVariant.Danger} onClick={onConfirm}>Eliminar y actualizar</Button></>}>
    <p>Esta acción también modificará:</p>
    <ul>{dependencies.map((dependency) => <li key={dependency}>{dependency}</li>)}</ul>
  </Modal>;
}

