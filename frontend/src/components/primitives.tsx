import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "outline" | "text" | "danger";

const buttonClasses: Record<ButtonVariant, string> = {
  primary: "ui-button--primary",
  secondary: "ui-button--secondary",
  outline: "ui-button--outline",
  text: "ui-button--text",
  danger: "ui-button--danger",
};

export function Button({ variant = "primary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return <button className={`ui-button ${buttonClasses[variant]} ${className}`.trim()} {...props} />;
}

export function Field({ label, hint, error, children }: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return <label className="ui-field">
    <span>{label}</span>
    {children}
    {hint && <small className="ui-field-hint">{hint}</small>}
    {error && <small className="ui-field-error" role="alert">{error}</small>}
  </label>;
}

export function EmptyState({ title, description, action }: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return <div className="empty-state">
    <h3>{title}</h3>
    {description && <p>{description}</p>}
    {action}
  </div>;
}

export function Skeleton({ label }: { label: string }) {
  return <div className="ui-skeleton" role="status" aria-label={label}><span aria-hidden="true" /></div>;
}

export function StatusBadge({ children, tone = "neutral" }: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
}) {
  return <span className={`ui-status-badge ui-status-badge--${tone}`}>{children}</span>;
}
