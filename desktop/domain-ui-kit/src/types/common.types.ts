import type { ReactNode } from "react";

export type SelectOption = { readonly value: string; readonly label: string; readonly disabled?: boolean };
export type FieldError = { readonly field: string; readonly message: string };
export type ComponentChildren = { readonly children: ReactNode };
