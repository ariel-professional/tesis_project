import type { ReactNode } from "react";

export type WizardItem<TStep extends string> = { readonly id: TStep; readonly label: string };

export function Wizard<TStep extends string>({ items, current, highestEnabledIndex, onSelect }: { items: readonly WizardItem<TStep>[]; current: TStep; highestEnabledIndex?: number; onSelect: (step: TStep) => void }) {
  const activeIndex = items.findIndex((item) => item.id === current);
  const enabledThrough = highestEnabledIndex ?? items.length - 1;
  return <nav className="ui-wizard" aria-label="Etapas del experimento">{items.map((item, index) => <button type="button" key={item.id} disabled={index > enabledThrough} className={item.id === current ? "is-active" : index <= enabledThrough ? "is-complete" : ""} onClick={() => onSelect(item.id)}><span>{index + 1}</span>{item.label}</button>)}</nav>;
}

export function SplitPane({ primary, secondary }: { primary: ReactNode; secondary: ReactNode }) {
  return <div className="ui-split"><div>{primary}</div><aside>{secondary}</aside></div>;
}
