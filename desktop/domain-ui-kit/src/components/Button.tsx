import type { ButtonHTMLAttributes } from "react";

export enum ButtonVariant {
  Primary = "primary",
  Secondary = "secondary",
  Danger = "danger",
  Ghost = "ghost",
}

export function Button({
  className = "",
  type = "button",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  const variant = props.variant ?? ButtonVariant.Primary;
  const { variant: _variant, ...buttonProps } = props;
  return <button type={type} className={`ui-button ui-button--${variant} ${className}`.trim()} {...buttonProps}>{children}</button>;
}

export function IconButton(props: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  const { label, className = "", children, ...buttonProps } = props;
  return <button type="button" aria-label={label} title={label} className={`ui-icon-button ${className}`.trim()} {...buttonProps}>{children}</button>;
}
