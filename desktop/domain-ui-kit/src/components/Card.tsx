import type { HTMLAttributes, ReactNode } from "react";

export function Card({ className = "", ...props }: HTMLAttributes<HTMLElement>) {
  return <article className={`ui-card ${className}`.trim()} {...props} />;
}

export function Panel({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`ui-panel ${className}`.trim()} {...props} />;
}

export function MetricCard({ label, value, style={} }: { label: string; value: ReactNode, style?: React.CSSProperties | undefined }) {
  return <div className="ui-metric" style={{...style}}><span>{label}</span><strong>{value}</strong></div>;
}

