import type { SelectOption } from "../types/common.types";

export enum ConfigurationKind {
  Integer = "integer",
  Boolean = "boolean",
  Select = "select",
  Readonly = "readonly",
}

export type BaseConfig<TDraft, TValue> = {
  readonly fieldName: string;
  readonly title: string;
  readonly description: string;
  readonly getValue: (draft: TDraft) => TValue;
  readonly setValue: (draft: TDraft, value: TValue) => TDraft;
};

export type ConfigurationOptionDefinition<TDraft> =
  | (BaseConfig<TDraft, number> & {
      readonly kind: ConfigurationKind.Integer;
      readonly min: number;
    })
  | (BaseConfig<TDraft, boolean> & { readonly kind: ConfigurationKind.Boolean })
  | (BaseConfig<TDraft, string> & {
      readonly kind: ConfigurationKind.Select;
      readonly options: readonly SelectOption[];
    })
  | {
      readonly kind: ConfigurationKind.Readonly;
      readonly fieldName: string;
      readonly title: string;
      readonly description: string;
      readonly getValue: (draft: TDraft) => string;
    };

export type ConfigurationSectionDefinition<TDraft> = {
  readonly id: string;
  readonly title: string;
  readonly description?: string;
  readonly options: readonly ConfigurationOptionDefinition<TDraft>[];
};

