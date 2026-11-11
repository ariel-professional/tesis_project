import type { ReactNode } from "react";

export function EntityTable({ headers, children, empty }: { headers: readonly string[]; children: ReactNode; empty?: boolean }) {
  if (empty === true) return <div className="ui-table-empty">Todavía no hay elementos.</div>;
  return <div className="ui-table-wrap"><table className="ui-table"><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;
}
