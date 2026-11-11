import { compileFromFile } from "json-schema-to-typescript";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "../..");
const targets = [
  [
    path.join(root, "desktop_schemas/1.5.0/gateway-message.schema.json"),
    path.join(root, "desktop/src/generated/gateway-message.d.ts"),
  ],
  [
    path.join(
      root,
      "domain_schemas/single-row-facility-layout/1.0.0/domain-experiment-config.schema.json",
    ),
    path.join(root, "desktop/src/generated/single-row-facility-layout.d.ts"),
  ],
  [
    path.join(root, "domain_schemas/single-row-facility-layout/1.0.0/single-row-facility-layout-result.schema.json"),
    path.join(root, "desktop/src/generated/single-row-facility-layout-result.d.ts"),
  ],
  [
    path.join(root, "domain_schemas/single-row-facility-layout/1.0.0/domain-run-manifest.schema.json"),
    path.join(root, "desktop/src/generated/single-row-facility-layout-run.d.ts"),
  ],
  [
    path.join(root, "domain_schemas/single-row-facility-layout/2.0.0/domain-experiment-config.schema.json"),
    path.join(root, "desktop/src/generated/single-row-facility-layout-v2.d.ts"),
  ],
  [
    path.join(root, "domain_schemas/single-row-facility-layout/2.0.0/single-row-facility-layout-result.schema.json"),
    path.join(root, "desktop/src/generated/single-row-facility-layout-result-v2.d.ts"),
  ],
  [
    path.join(root, "domain_schemas/single-row-facility-layout/2.0.0/domain-run-manifest.schema.json"),
    path.join(root, "desktop/src/generated/single-row-facility-layout-run-v2.d.ts"),
  ],
  [
    path.join(root, "domain_schemas/single-row-facility-layout/2.1.0/domain-experiment-config.schema.json"),
    path.join(root, "desktop/src/generated/single-row-facility-layout-v21.d.ts"),
  ],
  [
    path.join(root, "domain_schemas/single-row-facility-layout/2.1.0/single-row-facility-layout-result.schema.json"),
    path.join(root, "desktop/src/generated/single-row-facility-layout-result-v21.d.ts"),
  ],
  [
    path.join(root, "domain_schemas/single-row-facility-layout/2.1.0/domain-run-manifest.schema.json"),
    path.join(root, "desktop/src/generated/single-row-facility-layout-run-v21.d.ts"),
  ],
];

for (const [source, destination] of targets) {
  const output = await compileFromFile(source, {
    bannerComment: "/* Generated from JSON Schema. Do not edit. */",
    style: { singleQuote: false },
  });
  await mkdir(path.dirname(destination), { recursive: true });
  await writeFile(destination, output, "utf8");
}
