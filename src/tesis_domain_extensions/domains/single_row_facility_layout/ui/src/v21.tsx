import type React from "react";
import type { DomainUiHost, DomainUiModule } from "@domain-ui-sdk";
import { SingleRowFacilityLayoutScreen } from "./screen";

export const Screen: React.ComponentType<{ host: DomainUiHost }> = ({ host }) => (
  <SingleRowFacilityLayoutScreen host={host} version="2.1.0" />
);

export const module: DomainUiModule = { Screen };
