import { useState } from "react";

export function SearchableMultiSelect({ options, selected, onChange }: { options: readonly { value: string; label: string }[]; selected: readonly string[]; onChange: (selected: string[]) => void }) {
  const [query, setQuery] = useState("");
  const visible = options.filter((option) => `${option.value} ${option.label}`.toLocaleLowerCase("es").includes(query.trim().toLocaleLowerCase("es")));
  return <div className="ui-multiselect-wrap"><input className="ui-input" type="search" placeholder="Buscar adyacencias…" value={query} onChange={(event) => setQuery(event.target.value)} /><div className="ui-multiselect">{visible.map((option) => <label key={option.value}><input type="checkbox" checked={selected.includes(option.value)} onChange={() => onChange(selected.includes(option.value) ? selected.filter((value) => value !== option.value) : [...selected, option.value])} /><span>{option.label}</span></label>)}</div>{visible.length === 0 && <small>No hay coincidencias.</small>}</div>;
}
