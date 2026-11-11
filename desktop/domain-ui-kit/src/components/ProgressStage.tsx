import type { ReactNode } from "react";
export function ProgressStage({ title, description, active = false, complete = false, trailing }: { title: string; description: string; active?: boolean; complete?: boolean; trailing?: ReactNode }) {
  return <div className={`ui-progress-stage ${active ? "is-active" : ""} ${complete ? "is-complete" : ""}`}><span className="ui-progress-stage__dot" /><div><strong>{title}</strong><p>{description}</p></div>{trailing}</div>;
}
