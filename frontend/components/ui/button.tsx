import type { ButtonHTMLAttributes, AnchorHTMLAttributes, ReactNode } from "react";
import Link from "next/link";

type ButtonVariant = "primary" | "accent-light" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg" | "icon";

interface SharedProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  children?: ReactNode;
}

interface ButtonProps
  extends SharedProps,
    Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children" | "size"> {}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] border-transparent",
  "accent-light":
    "bg-[var(--color-accent-light)] text-[var(--color-text-primary)] hover:bg-[var(--color-accent-soft)] border-transparent",
  secondary:
    "bg-transparent text-[var(--color-text-primary)] border-[var(--color-border)] hover:bg-[var(--color-bg-page)]",
  ghost:
    "bg-transparent text-[var(--color-text-secondary)] border-transparent hover:bg-[var(--color-bg-page)]",
  danger:
    "bg-[var(--color-danger)] text-white hover:opacity-90 border-transparent",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs rounded-md",
  md: "px-3.5 py-2 text-sm rounded-lg",
  lg: "px-4 py-2.5 text-sm rounded-lg",
  icon: "p-2 rounded-lg",
};

const baseClasses =
  "inline-flex items-center justify-center gap-2 font-medium border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-soft)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-page)] disabled:opacity-50 disabled:cursor-not-allowed";

function buildClassName(
  variant: ButtonVariant,
  size: ButtonSize,
  className?: string
) {
  return [baseClasses, variantClasses[variant], sizeClasses[size], className]
    .filter(Boolean)
    .join(" ");
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button className={buildClassName(variant, size, className)} {...props}>
      {children}
    </button>
  );
}

interface ButtonLinkProps
  extends SharedProps,
    Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "className" | "children" | "size"> {
  href: string;
}

export function ButtonLink({
  href,
  variant = "primary",
  size = "md",
  className,
  children,
  ...props
}: ButtonLinkProps) {
  return (
    <Link
      href={href}
      className={buildClassName(variant, size, className)}
      {...props}
    >
      {children}
    </Link>
  );
}
