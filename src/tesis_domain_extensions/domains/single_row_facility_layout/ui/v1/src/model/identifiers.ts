let keySequence = 0;
export function nextClientKey(prefix: string): string { keySequence += 1; return `${prefix}-${keySequence}`; }

export function slugify(value: string, fallback: string): string {
  const slug = value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return slug || fallback;
}

export function uniqueIdentifier(candidate: string, used: readonly string[]): string {
  if (!used.includes(candidate)) return candidate;
  let suffix = 2;
  while (used.includes(`${candidate}-${suffix}`)) suffix += 1;
  return `${candidate}-${suffix}`;
}

export function newStudyIdentifier(): string {
  return `study-${crypto.randomUUID()}`;
}
