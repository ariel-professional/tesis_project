export type ExactFractionValue = {
  numerator: number | string;
  denominator: number | string;
};

import { formatCount } from "../../model/display-values";

export type FractionDetailParts = {
  beforeRepeat: string;
  repeating: string | null;
  afterRepeat: string;
};

function parts(value: ExactFractionValue): {
  numerator: bigint;
  denominator: bigint;
  negative: boolean;
} | null {
  try {
    let numerator = BigInt(value.numerator);
    let denominator = BigInt(value.denominator);
    if (denominator === 0n) return null;
    const negative = (numerator < 0n) !== (denominator < 0n);
    if (numerator < 0n) numerator = -numerator;
    if (denominator < 0n) denominator = -denominator;
    return { numerator, denominator, negative };
  } catch {
    return null;
  }
}

export function formatFractionDecimal(
  value: ExactFractionValue | null | undefined,
  maximumFractionDigits = 6,
): string {
  if (value == null) return "—";
  const parsed = parts(value);
  if (parsed === null) return "—";
  const { numerator, denominator, negative } = parsed;
  const scale = 10n ** BigInt(maximumFractionDigits);
  const rounded = (numerator * scale + denominator / 2n) / denominator;
  if (rounded === 0n && numerator !== 0n) {
    const threshold = `0,${"0".repeat(Math.max(0, maximumFractionDigits - 1))}1`;
    return negative ? `> −${threshold}` : `< ${threshold}`;
  }
  const integer = rounded / scale;
  const decimals = String(rounded % scale)
    .padStart(maximumFractionDigits, "0")
    .replace(/0+$/u, "");
  return `${negative ? "−" : ""}${integer}${decimals === "" ? "" : `,${decimals}`}`;
}

export function formatFractionDetailParts(
  value: ExactFractionValue | null | undefined,
): FractionDetailParts {
  if (value == null) return { beforeRepeat: "Inconcluso", repeating: null, afterRepeat: "" };
  const rational = `${formatCount(value.numerator)}/${formatCount(value.denominator)}`;
  const parsed = parts(value);
  if (parsed === null) return { beforeRepeat: rational, repeating: null, afterRepeat: "" };
  const { numerator, denominator, negative } = parsed;
  const integer = numerator / denominator;
  let remainder = numerator % denominator;
  if (remainder === 0n) {
    return {
      beforeRepeat: `${negative ? "−" : ""}${integer}`,
      repeating: null,
      afterRepeat: "",
    };
  }

  const digits: string[] = [];
  const positions = new Map<bigint, number>();
  const maxDigits = 160;
  while (remainder !== 0n && !positions.has(remainder) && digits.length < maxDigits) {
    positions.set(remainder, digits.length);
    remainder *= 10n;
    digits.push(String(remainder / denominator));
    remainder %= denominator;
  }
  const prefix = `${negative ? "−" : ""}${integer},`;
  if (remainder === 0n) {
    return {
      beforeRepeat: `${rational} = ${prefix}${digits.join("")}`,
      repeating: null,
      afterRepeat: "",
    };
  }
  const repeatAt = positions.get(remainder);
  if (repeatAt !== undefined) {
    const nonRepeating = digits.slice(0, repeatAt).join("");
    return {
      beforeRepeat: `${rational} = ${prefix}${nonRepeating}`,
      repeating: digits.slice(repeatAt).join(""),
      afterRepeat: "",
    };
  }
  return {
    beforeRepeat: `${rational} ≈ ${prefix}${digits.slice(0, 24).join("")}…`,
    repeating: null,
    afterRepeat: "",
  };
}
