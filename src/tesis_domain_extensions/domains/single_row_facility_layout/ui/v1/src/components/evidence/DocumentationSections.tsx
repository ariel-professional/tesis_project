import type { ReactNode } from "react";

type Entry = { key: string; title: string; content: ReactNode };

export function DocumentationSections({ study, designs, restrictions }: { study: Entry; designs: Entry[]; restrictions: Entry[] }) {
  const groups = [
    { title: "Estudio", entries: [study] },
    { title: "Diseños", entries: designs },
    { title: "Restricciones", entries: restrictions },
  ];
  return <div className="srfl-documentation-groups">{groups.map(({ title, entries }) =>
    <section className="srfl-documentation-group" key={title} aria-label={`Antecedentes: ${title}`}>
      <header><h3>{title}</h3><span>{entries.length}</span></header>
      {entries.length === 0 ? <p className="srfl-documentation-empty">No hay {title.toLowerCase()} en esta selección.</p> :
        entries.map((entry) => <article className="srfl-documentation-entry" key={entry.key}><h4>{entry.title}</h4>{entry.content}</article>)}
    </section>,
  )}</div>;
}
