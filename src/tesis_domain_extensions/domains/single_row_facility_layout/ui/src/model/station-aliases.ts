import type { EditableStation } from "./editor-draft.types";

export function orderedStations(
  stations: readonly EditableStation[],
  displayOrder: readonly string[],
): EditableStation[] {
  const byKey = new Map(stations.map((station) => [station.clientKey, station]));
  const ordered = displayOrder.flatMap((key) => {
    const station = byKey.get(key);
    if (station === undefined) return [];
    byKey.delete(key);
    return [station];
  });
  return [...ordered, ...stations.filter((station) => byKey.has(station.clientKey))];
}

export function stationAliases(
  stations: readonly EditableStation[],
): ReadonlyMap<string, string> {
  const names = stations.map((station) => station.name.trim());
  const aliases = new Map<string, string>();
  const used = new Set<string>();
  const groups = new Map<string, EditableStation[]>();
  for (const station of stations) {
    const name = station.name.trim();
    groups.set(name, [...(groups.get(name) ?? []), station]);
  }
  for (const [name, group] of [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    const characters = Array.from(name || "?");
    let length = 1;
    while (
      length < characters.length
      && names.some((other) => other !== name && Array.from(other).slice(0, length).join("") === characters.slice(0, length).join(""))
    ) length += 1;
    const base = characters.slice(0, length).join("");
    const sorted = [...group].sort((a, b) => a.id.localeCompare(b.id) || a.clientKey.localeCompare(b.clientKey));
    for (const [index, station] of sorted.entries()) {
      let candidate = sorted.length === 1 ? base : `${base}${index + 1}`;
      let suffix = sorted.length === 1 ? 2 : index + 2;
      while (used.has(candidate)) candidate = `${base}${suffix++}`;
      used.add(candidate);
      aliases.set(station.clientKey, candidate);
    }
  }
  return aliases;
}
