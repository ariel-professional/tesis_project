import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Button, ButtonVariant, IconButton } from "./Button";

/** A shared semantic vocabulary for actions whose icon must stay consistent. */
export type ActionIconName =
  | "resume"
  | "view-details"
  | "view-results"
  | "next"
  | "previous"
  | "copy"
  | "paste"
  | "duplicate"
  | "delete"
  | "calculate"
  | "cancel"
  | "open"
  | "validate";

const paths: Record<ActionIconName, ReactNode> = {
  resume: <><path d="M3 12a9 9 0 1 0 2.64-6.36L3 8" /><path d="M3 3v5h5" /></>,
  "view-details": <><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
  "view-results": <><path d="M4 19V5m0 14h16" /><path d="M7 15v-3m4 3V8m4 7V5m4 10v-5" /></>,
  next: <><path d="M4 12h16" /><path d="m13 5 7 7-7 7" /></>,
  previous: <><path d="M20 12H4" /><path d="m11 5-7 7 7 7" /></>,
  copy: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" /></>,
  paste: <><path d="M8 4h8l1 2h3v14H4V6h3l1-2Z" /><path d="M9 4a3 3 0 0 1 6 0M8 11h8m-8 4h8" /></>,
  duplicate: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" /><path d="M14 11v6m-3-3h6" /></>,
  delete: <><path d="M3 6h18M8 6V4h8v2m3 0-.9 14H5.9L5 6m4 4v6m6-6v6" /></>,
  calculate: <><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 7h8M8 12h2m4 0h2m-8 4h2m4 0h2" /></>,
  cancel: <><rect x="4" y="4" width="16" height="16" rx="3" /></>,
  open: <><path d="M14 4h6v6m0-6-9 9" /><path d="M18 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5" /></>,
  validate: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16.5 9" /></>,
};

export function ActionIcon({ action }: { action: ActionIconName }) {
  return <svg className="ui-action-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[action]}</svg>;
}

type SharedProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  action: ActionIconName;
  label: string;
  children?: ReactNode;
  loading?: boolean;
};

function ActionGlyph({ action, loading }: { action: ActionIconName; loading: boolean }) {
  return loading
    ? <span className="ui-action-spinner" aria-hidden="true" />
    : <ActionIcon action={action} />;
}

/** Standard button with the kit's icon for its semantic action. */
export function ActionButton({ action, label, children, className = "", loading = false, disabled = false, "aria-busy": ariaBusy, ...props }: SharedProps & { variant?: ButtonVariant }) {
  return <Button {...props} className={`ui-button--with-icon ${className}`.trim()} disabled={disabled || loading} aria-busy={loading || ariaBusy}><ActionGlyph action={action} loading={loading} />{children ?? label}</Button>;
}

/** Standard icon-only button with the kit's icon for its semantic action. */
export function ActionIconButton({ action, label, children, loading = false, disabled = false, "aria-busy": ariaBusy, ...props }: SharedProps) {
  return <IconButton {...props} label={label} disabled={disabled || loading} aria-busy={loading || ariaBusy}><ActionGlyph action={action} loading={loading} />{loading ? null : children}</IconButton>;
}
