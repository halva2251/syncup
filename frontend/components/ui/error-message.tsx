import type { ReactNode } from "react";

interface ErrorMessageProps {
  children?: ReactNode;
  className?: string;
}

export function ErrorMessage({ children, className }: ErrorMessageProps) {
  if (!children) return null;

  return (
    <div
      className={[
        "rounded-lg border border-[var(--color-danger)]/20 bg-[var(--color-danger)]/10 px-3 py-2.5 text-sm text-[var(--color-danger)]",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </div>
  );
}
