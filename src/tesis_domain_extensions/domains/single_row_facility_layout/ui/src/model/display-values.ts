export function formatCount(value: number | string | bigint | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return BigInt(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

const PREFIXES: Record<number, string> = {
  3: "kilo", 6: "mega", 9: "giga", 12: "tera", 15: "peta",
  18: "exa", 21: "zetta", 24: "yotta", 27: "ronna", 30: "quetta",
};
const SUPER = "⁰¹²³⁴⁵⁶⁷⁸⁹";

export function formatEngineeringCount(value: number | string | bigint | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const exact = formatCount(value);
  const digits = BigInt(value).toString();
  if (BigInt(value) < 1_000_000n) return exact;
  const exponent = Math.floor((digits.length - 1) / 3) * 3;
  const whole = digits.slice(0, digits.length - exponent);
  const decimal = digits.slice(digits.length - exponent).slice(0, 3).replace(/0+$/, "");
  const approximate = `${whole}${decimal ? `,${decimal}` : ""}`;
  const suffix = PREFIXES[exponent];
  return `${exact} (≈ ${suffix ? `${approximate} ${suffix}-combinaciones` : `${approximate} × 10${String(exponent).split("").map((digit) => SUPER[Number(digit)]).join("")} combinaciones`})`;
}

export function formatDuration(milliseconds: number | bigint): string {
  const seconds = (typeof milliseconds === "bigint" ? milliseconds : BigInt(Math.floor(milliseconds))) / 1000n;
  if (seconds < 60n) return `${seconds} s`;
  const units: [bigint, string][] = [[86_400n, "día"], [3_600n, "h"], [60n, "min"], [1n, "s"]];
  const parts: string[] = [];
  let remaining = seconds;
  for (const [size, unit] of units) {
    const amount = remaining / size;
    remaining %= size;
    if (amount > 0n && parts.length < 2) parts.push(`${amount} ${unit}${unit === "día" && amount !== 1n ? "s" : ""}`);
  }
  return parts.join(" ");
}
