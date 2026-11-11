import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  status,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  status?: ReactNode;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="ui-page-header">
      <div>
        {eyebrow !== undefined && <span className="ui-eyebrow">{eyebrow}</span>}
        <div className="ui-page-header__title">
          <h1>{title}</h1>
          {status}
        </div>
        {description !== undefined && <p>{description}</p>}
      </div>
      {actions !== undefined && (
        <div className="ui-page-header__actions">{actions}</div>
      )}
    </header>
  );
}

export function EmptyState({
  title,
  description,
  actions,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="ui-empty">
      <div className="ui-empty__mark">◇</div>
      <h3>{title}</h3>
      <p>{description}</p>
      {actions}
    </div>
  );
}

export function StatusBadge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
}) {
  return <span className={`ui-status ui-status--${tone}`}>{children}</span>;
}
