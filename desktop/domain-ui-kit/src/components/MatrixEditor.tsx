import { useRef, type KeyboardEvent, type ReactNode } from "react";

export type MatrixEditorMode = "full" | "triangular";
export type MatrixEditorCell = { rowId: string; columnId: string };

export type MatrixEditorProps = {
  rows: readonly { id: string; label: string }[];
  columns?: readonly { id: string; label: string }[];
  mode: MatrixEditorMode;
  label: string;
  activeCell?: MatrixEditorCell | null;
  selectedCells?: readonly MatrixEditorCell[];
  editingCell?: MatrixEditorCell | null;
  invalid?: boolean;
  renderCell: (rowId: string, columnId: string, readOnly: boolean) => ReactNode;
  renderEditor?: (rowId: string, columnId: string) => ReactNode;
  onActivate?: (rowId: string, columnId: string) => void;
  onToggleCell?: (rowId: string, columnId: string) => void;
  onEditCell?: (rowId: string, columnId: string) => void;
};

/** A domain-neutral, accessible matrix shell. Domains own their cell values and editors. */
export function MatrixEditor({ rows, columns = rows, mode, label, activeCell = null, selectedCells = [], editingCell, invalid = false, renderCell, renderEditor, onActivate, onToggleCell, onEditCell }: MatrixEditorProps) {
  const table = useRef<HTMLTableElement>(null);
  const cellToken = (rowId: string, columnId: string) =>
    `${encodeURIComponent(rowId)}::${encodeURIComponent(columnId)}`;
  const selected = new Set(selectedCells.map((cell) => `${cell.rowId}\0${cell.columnId}`));
  const visible = (row: number, column: number) => row !== column && (mode === "full" || column > row);
  const move = (row: number, column: number, direction: "up" | "down" | "left" | "right") => {
    let nextRow = row; let nextColumn = column;
    do {
      if (direction === "up") nextRow -= 1;
      if (direction === "down") nextRow += 1;
      if (direction === "left") nextColumn -= 1;
      if (direction === "right") nextColumn += 1;
    } while (nextRow >= 0 && nextColumn >= 0 && nextRow < rows.length && nextColumn < columns.length && !visible(nextRow, nextColumn));
    if (nextRow >= 0 && nextColumn >= 0 && nextRow < rows.length && nextColumn < columns.length) {
      const nextRowItem = rows[nextRow]; const nextColumnItem = columns[nextColumn];
      if (nextRowItem === undefined || nextColumnItem === undefined) return;
      onActivate?.(nextRowItem.id, nextColumnItem.id);
      table.current?.querySelector<HTMLButtonElement>(`[data-matrix-cell="${cellToken(nextRowItem.id, nextColumnItem.id)}"]`)?.focus();
    }
  };
  const keyDown = (event: KeyboardEvent<HTMLButtonElement>, row: number, column: number) => {
    const rowItem = rows[row]; const columnItem = columns[column];
    if (rowItem === undefined || columnItem === undefined) return;
    if (event.key === " " && onToggleCell !== undefined) { event.preventDefault(); onToggleCell(rowItem.id, columnItem.id); return; }
    if (event.key === "Enter" && onEditCell !== undefined) { event.preventDefault(); onEditCell(rowItem.id, columnItem.id); return; }
    const directions = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right" } as const;
    const direction = directions[event.key as keyof typeof directions];
    if (direction !== undefined) { event.preventDefault(); move(row, column, direction); }
  };
  return <div className="ui-matrix-wrap" aria-invalid={invalid || undefined}>
    <table ref={table} className="ui-matrix" aria-label={label}>
      <thead><tr><th scope="col">{label}</th>{columns.map((column) => <th key={column.id} scope="col">{column.label}</th>)}</tr></thead>
      <tbody>{rows.map((row, rowIndex) => <tr key={row.id}><th scope="row">{row.label}</th>{columns.map((column, columnIndex) => {
        if (!visible(rowIndex, columnIndex)) return <td key={column.id} className="ui-matrix__disabled" aria-label={rowIndex === columnIndex ? "Diagonal no editable" : "Celda reflejada"}>—</td>;
        const current = activeCell?.rowId === row.id && activeCell.columnId === column.id;
        const isSelected = selected.has(`${row.id}\0${column.id}`);
        const isEditing = editingCell?.rowId === row.id && editingCell.columnId === column.id;
        const directEditor = renderEditor !== undefined && editingCell === undefined;
        const cellClassName = [current ? "is-active" : "", isSelected ? "is-selected" : "", isEditing ? "is-editing" : "", renderEditor !== undefined ? "ui-matrix__editable-cell" : ""].filter(Boolean).join(" ");
        return <td key={column.id} className={cellClassName}>{renderEditor !== undefined && (directEditor || isEditing)
          ? <div className="ui-matrix__direct-cell" onFocus={() => onActivate?.(row.id, column.id)}>{renderEditor(row.id, column.id)}</div>
          : <button type="button" className="ui-matrix__cell" data-matrix-cell={cellToken(row.id, column.id)} aria-label={`${row.label}, ${column.label}`} aria-pressed={isSelected || current} onKeyDown={(event) => keyDown(event, rowIndex, columnIndex)} onClick={(event) => { if (event.detail > 1) return; if (onToggleCell !== undefined) onToggleCell(row.id, column.id); else onActivate?.(row.id, column.id); }} onDoubleClick={() => onEditCell?.(row.id, column.id)}>{renderCell(row.id, column.id, false)}</button>}
        </td>;
      })}</tr>)}</tbody>
    </table>
  </div>;
}
