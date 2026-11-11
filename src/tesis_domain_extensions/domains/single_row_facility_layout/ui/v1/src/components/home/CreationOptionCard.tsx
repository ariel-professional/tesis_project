import { ActionButton, Button, ButtonVariant, Card, type ActionIconName } from "@domain-ui-kit";
import type { ReactNode } from "react";

export function CreationOptionCard({ icon, title, description, action, actionLabel, actionIcon, variant = ButtonVariant.Primary }: { icon: string; title: string; description: string; action: () => void; actionLabel: string; actionIcon?: ActionIconName; variant?: ButtonVariant }) {
  return <Card className="srfl-creation-card"><span className="srfl-creation-card__icon" aria-hidden="true">{icon}</span><h2>{title}</h2><p>{description}</p>{actionIcon ? <ActionButton action={actionIcon} label={actionLabel} variant={variant} onClick={action} /> : <Button variant={variant} onClick={action}>{actionLabel}</Button>}</Card>;
}

export function HomeSection({ title, children }: { title: string; children: ReactNode }) {
  return <section className="srfl-home-section"><h2>{title}</h2>{children}</section>;
}

