import type { LayoutCaseResult } from "@domain-ui-sdk";
import { useState } from "react";

function value(caseResult: LayoutCaseResult): bigint | null {
  const raw = caseResult.compatible_layout_count?.value;
  return raw === null || raw === undefined ? null : BigInt(raw);
}

function coordinate(
  current: bigint,
  values: readonly bigint[],
  inverted = false,
): number {
  const min = values.reduce((left, right) => (left < right ? left : right));
  const max = values.reduce((left, right) => (left > right ? left : right));
  const scaled =
    max === min ? 50 : Number(((current - min) * 10_000n) / (max - min)) / 100;
  return inverted ? 90 - scaled * 0.75 : 10 + scaled * 0.75;
}

export function DesignComparison({
  cases,
  onSelect,
}: {
  cases: readonly LayoutCaseResult[];
  onSelect: (item: LayoutCaseResult) => void;
}) {
  const [showFrontier, setShowFrontier] = useState(true);
  const points = cases.flatMap((item) => {
    const layouts = value(item);
    return layouts === null
      ? []
      : [{ item, utility: BigInt(item.total_utility), layouts }];
  });
  const utilities = points.map((point) => point.utility);
  const layouts = points.map((point) => point.layouts);
  const position = (utility: bigint, count: bigint) => ({
    x: 64 + coordinate(utility, utilities) * 5.8,
    y: coordinate(count, layouts, true) * 3.4,
  });
  const frontier = points
    .filter((point) => point.item.pareto_optimal)
    .sort((left, right) =>
      left.utility < right.utility ? -1 : left.utility > right.utility ? 1 : 0,
    );
  return (
    <section
      className="srfl-result-chart"
      aria-label="Utilidad y disposiciones compatibles"
    >
      <header>
        <div>
          <h3>Layouts disponibles vs Utilidad</h3>
          <p>
            Cada punto representa un caso. <br /> Los puntos destacados pertenecen al
            frente de Pareto.
          </p>
        </div>
        {frontier.length > 1 && (
          <label className="srfl-frontier-toggle">
            <input
              type="checkbox"
              checked={showFrontier}
              onChange={(event) => setShowFrontier(event.target.checked)}
            />{" "}
            Trazar frente de Pareto
          </label>
        )}
      </header>
      {points.length === 0 ? (
        <p>No hay conteos concluyentes para graficar.</p>
      ) : (
        <svg
          viewBox="0 0 600 390"
          role="img"
          aria-label="Gráfico de utilidad contra layouts disponibles"
        >
          <line x1="64" y1="28" x2="64" y2="320" />
          <line x1="64" y1="320" x2="570" y2="320" />
          <text x="317" y="372">
            Utilidad total
          </text>
          <text x="18" y="174" transform="rotate(-90 18 174)">
            Layouts disponibles
          </text>
          {showFrontier && frontier.length > 1 && (
            <polyline
              className="srfl-pareto-frontier"
              points={frontier
                .map(({ utility, layouts: count }) => {
                  const point = position(utility, count);
                  return `${point.x},${point.y}`;
                })
                .join(" ")}
            />
          )}
          {points.map(({ item, utility, layouts: count }) => {
            const point = position(utility, count);
            return (
              <circle
                key={item.case_id}
                className={item.pareto_optimal ? "is-pareto" : ""}
                cx={point.x}
                cy={point.y}
                r={item.pareto_optimal ? 7 : 5}
                tabIndex={0}
                onClick={() => onSelect(item)}
              >
                <title>{`Utilidad ${utility.toLocaleString("es-AR")} · ${count.toLocaleString("es-AR")} layouts`}</title>
              </circle>
            );
          })}
        </svg>
      )}
    </section>
  );
}
