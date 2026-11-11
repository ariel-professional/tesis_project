import { expect, test } from "vitest";
import { formatCount, formatDuration, formatEngineeringCount } from "@srfl-ui/model/display-values";
import { formatFractionDetailParts } from "@srfl-ui/components/results/format-fraction";

test("large counts keep exact thousands and add engineering scale", () => {
  expect(formatCount("1290240")).toBe("1.290.240");
  expect(formatEngineeringCount("10461394944000")).toBe("10.461.394.944.000 (≈ 10,461 tera-combinaciones)");
  expect(formatEngineeringCount("23040")).toBe("23.040");
  expect(formatEngineeringCount(`83${"0".repeat(222)}`)).toContain("× 10²²² combinaciones");
  expect(formatFractionDetailParts({ numerator: 1, denominator: 454053600 }).beforeRepeat).toContain("1/454.053.600");
});

test("durations cross minute, hour and day boundaries", () => {
  expect(formatDuration(45_000)).toBe("45 s");
  expect(formatDuration(72_000)).toBe("1 min 12 s");
  expect(formatDuration(7_500_000)).toBe("2 h 5 min");
  expect(formatDuration(97_200_000)).toBe("1 día 3 h");
});
