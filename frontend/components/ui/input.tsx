import type { InputHTMLAttributes } from "react";

interface InputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "className"> {
  label?: string;
  error?: string;
  className?: string;
}

export function Input({
  label,
  error,
  className,
  id,
  ...props
}: InputProps) {
  const inputId = id ?? (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

  return (
    <div className={className}>
      {label && (
        <label
          htmlFor={inputId}
          className="mb-2 block text-[15px] font-medium text-[var(--color-text-primary)]"
        >
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={[
          "w-full rounded-lg border bg-[var(--color-bg-card)] px-3.5 py-2 text-[15px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)]",
          "h-[42px] transition-colors",
          "focus:outline-none focus:border-[var(--color-accent)] focus:ring-[3px] focus:ring-[var(--color-accent-soft)]",
          error
            ? "border-[var(--color-danger)] focus:border-[var(--color-danger)] focus:ring-red-100"
            : "border-[var(--color-border)]",
        ].join(" ")}
        {...props}
      />
      {error && (
        <p className="mt-1.5 text-xs text-[var(--color-danger)]">{error}</p>
      )}
    </div>
  );
}
