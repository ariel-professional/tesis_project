export enum SrflEditorStep {
  Information = "information",
  Criteria = "criteria",
  Stations = "stations",
  Relations = "relations",
  Adjacencies = "adjacencies",
  Designs = "designs",
  AdvancedConfiguration = "advanced-configuration",
  Review = "review",
}

export enum SrflScreenMode {
  Home = "home",
  Editor = "editor",
  Execution = "execution",
  Results = "results",
  Runs = "runs",
}

export enum DraftOriginKind {
  Empty = "empty",
  Template = "template",
  ImportedFile = "imported-file",
  PastedJson = "pasted-json",
}

export enum FieldValidationState {
  Pristine = "pristine",
  Valid = "valid",
  Invalid = "invalid",
}
