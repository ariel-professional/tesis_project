import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import type { SelectOption } from "../types/common.types";

type FieldFrameProps = {
  label: string;
  fieldName?: string;
  description?: string;
  helperText?: string;
  error?: string;
};

function FieldFrame({ label, fieldName, description, helperText, error, children }: FieldFrameProps & { children: React.ReactNode }) {
  return <label className="ui-field">
    <span className="ui-field__label">{label}</span>
    {description !== undefined && <span className="ui-field__description">{description}</span>}
    {children}
    {helperText !== undefined && <span className="ui-field__helper">{helperText}</span>}
    {fieldName !== undefined && <span className="ui-field__path"><code>{fieldName}</code></span>}
    {error !== undefined && <span className="ui-field__error">{error}</span>}
  </label>;
}

export function TextField(props: FieldFrameProps & InputHTMLAttributes<HTMLInputElement>) {
  const { label, fieldName, description, helperText, error, className = "", ...inputProps } = props;
  return <FieldFrame {...{ label, fieldName, description, helperText, error }}><input className={`ui-input ${className}`.trim()} {...inputProps} aria-label={inputProps["aria-label"] ?? (helperText !== undefined ? label : undefined)} /></FieldFrame>;
}

export function NumberField(props: FieldFrameProps & InputHTMLAttributes<HTMLInputElement>) {
  return <TextField {...props} aria-label={props["aria-label"] ?? props.label} type="number" />;
}

export function TextAreaField(props: FieldFrameProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { label, fieldName, description, helperText, error, className = "", rows = 5, ...textareaProps } = props;
  return <FieldFrame {...{ label, fieldName, description, helperText, error }}><textarea className={`ui-input ui-textarea ${className}`.trim()} rows={rows} {...textareaProps} aria-label={textareaProps["aria-label"] ?? (helperText !== undefined ? label : undefined)} /></FieldFrame>;
}

export function SelectField(props: FieldFrameProps & SelectHTMLAttributes<HTMLSelectElement> & { options: readonly SelectOption[] }) {
  const { label, fieldName, description, helperText, error, options, className = "", ...selectProps } = props;
  return <FieldFrame {...{ label, fieldName, description, helperText, error }}><select className={`ui-input ${className}`.trim()} {...selectProps} aria-label={selectProps["aria-label"] ?? (helperText !== undefined ? label : undefined)}>{options.map((option) => <option key={option.value} value={option.value} disabled={option.disabled}>{option.label}</option>)}</select></FieldFrame>;
}

export function SwitchField({ label, fieldName, description, error, checked, onChange, disabled }: FieldFrameProps & { checked: boolean; onChange: (checked: boolean) => void; disabled?: boolean }) {
  return <FieldFrame {...{ label, fieldName, description, error }}><button type="button" role="switch" aria-label={label} aria-checked={checked} disabled={disabled} className="ui-switch" onClick={() => onChange(!checked)}><span /></button></FieldFrame>;
}
