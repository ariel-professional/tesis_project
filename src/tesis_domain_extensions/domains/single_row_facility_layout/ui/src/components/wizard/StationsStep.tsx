import type { SrflEditorDraft } from "../../model/editor-draft.types";
import { StationTable } from "../stations/StationTable";
export function StationsStep({ draft, onChange }: { draft: SrflEditorDraft; onChange: (draft: SrflEditorDraft) => void }) { return <section className="srfl-step"><div className="srfl-step__intro"><h2>Estaciones</h2><p>Agregá las áreas o sectores que pueden participar de una disposición lineal.</p></div><StationTable draft={draft} onChange={onChange} /></section>; }

