import type React from "react";
import type { DomainUiHost } from "./host";

export type { LayoutReporting, SingleRowFacilityLayoutConfig as SingleRowFacilityLayoutDraft } from "../../src/generated/single-row-facility-layout";
export type { SingleRowFacilityLayoutConfigV2 as SingleRowFacilityLayoutDraftV2, ExecutionConfig } from "../../src/generated/single-row-facility-layout-v2";
export type {
  SingleRowFacilityLayoutConfigV21 as SingleRowFacilityLayoutDraftV21,
  ExecutionConfigV21,
} from "../../src/generated/single-row-facility-layout-v21";
export type { LayoutCaseResult, SingleRowFacilityLayoutResult, Station } from "../../src/generated/single-row-facility-layout-result";
export type { LayoutCaseResultV2, LayoutDesignResultV2, SingleRowFacilityLayoutResultV2, StationV2 } from "../../src/generated/single-row-facility-layout-result-v2";
export type {
  LayoutCaseResultV21,
  LayoutDesignResultV21,
  SingleRowFacilityLayoutResultV21,
  StationV2 as StationV21,
} from "../../src/generated/single-row-facility-layout-result-v21";
export type SingleRowFacilityLayoutDomainRun =
  | import("../../src/generated/single-row-facility-layout-run").DomainRunManifest
  | import("../../src/generated/single-row-facility-layout-run-v2").DomainRunManifestV2
  | import("../../src/generated/single-row-facility-layout-run-v21").DomainRunManifestV21;
export * from "./events";
export * from "./host";
export * from "./runs";
export * from "./templates";

export type DomainIdentity = { readonly id: string; readonly version: string };
export interface DomainUiModule { Screen: React.ComponentType<{ host: DomainUiHost }> }

export * from "./evidence";
