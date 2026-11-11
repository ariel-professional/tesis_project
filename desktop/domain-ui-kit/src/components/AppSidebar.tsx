import type { ReactNode } from "react";

export type SidebarItem<TValue extends string> = { readonly value: TValue; readonly label: string; readonly icon: string };
export function AppSidebar<TValue extends string>({ title, subtitle, items, active, onSelect, footer }: { title: string; subtitle: string; items: readonly SidebarItem<TValue>[]; active: TValue; onSelect: (value: TValue) => void; footer?: ReactNode }) {
  return <aside className="ui-sidebar"><div className="ui-sidebar__brand"><span className="ui-sidebar__logo">T</span><div><strong>{title}</strong><small>{subtitle}</small></div></div><nav>{items.map((item) => <button type="button" key={item.value} className={active === item.value ? "is-active" : ""} onClick={() => onSelect(item.value)}><span aria-hidden="true">{item.icon}</span>{item.label}</button>)}</nav>{footer !== undefined && <footer>{footer}</footer>}</aside>;
}
