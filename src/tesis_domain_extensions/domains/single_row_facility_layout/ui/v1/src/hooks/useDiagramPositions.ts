import { useEffect, useState } from "react";

export type DiagramPoint = { x: number; y: number };
export function useDiagramPositions(ids: readonly string[]) {
  const [positions, setPositions] = useState<Record<string, DiagramPoint>>({});
  useEffect(() => {
    setPositions((current) => {
      const next: Record<string, DiagramPoint> = {};
      ids.forEach((id, index) => {
        const angle = (Math.PI * 2 * index) / Math.max(ids.length, 1) - Math.PI / 2;
        next[id] = current[id] ?? { x: 300 + Math.cos(angle) * 205, y: 220 + Math.sin(angle) * 155 };
      });
      return next;
    });
  }, [ids.join("|")]);
  const move = (id: string, point: DiagramPoint) => setPositions((current) => ({ ...current, [id]: point }));
  return { positions, move };
}

