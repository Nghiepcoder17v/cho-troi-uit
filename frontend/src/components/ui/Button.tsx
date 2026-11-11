import type { ReactNode, ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "outline" | "text";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /**
   * Visual variant of the button.
   * - `primary`   – solid background using `--color-primary`.
   * - `secondary` – solid background using `--color-secondary`.
   * - `outline`   – border only, transparent background.
   * - `text`      – minimal text button (used for navigation links).
   */
  variant?: Variant;
  /** Button content */
  children: ReactNode;
}

/**
 * Shared UI button component.
 *
 * It composes a native `<button>` element and adds variant‑specific class names.
 * Existing CSS already defines `.outline-button` and `.text-button` styles; the
 * default `.button` style is applied for the `primary` and `secondary` variants.
 */
export function Button({ variant = "primary", className = "", ...rest }: ButtonProps) {
  const classes = [
    "button",
    variant === "primary" ? "" : // default button already styled as primary
    variant === "secondary" ? "secondary-button" :
    variant === "outline" ? "outline-button" :
    variant === "text" ? "text-button" :
    "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <button className={classes} {...rest} />;
}
