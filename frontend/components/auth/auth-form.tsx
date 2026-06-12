"use client";

import { useActionState } from "react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorMessage } from "@/components/ui/error-message";
import { Loader2 } from "lucide-react";

interface AuthField {
  name: string;
  label: string;
  type?: string;
  placeholder?: string;
  required?: boolean;
  autoComplete?: string;
}

interface AuthFormProps {
  action: (formData: FormData) => Promise<{ error?: string }>;
  title: string;
  subtitle: string;
  fields: AuthField[];
  submitLabel: string;
  footer: ReactNode;
}

export function AuthForm({
  action,
  title,
  subtitle,
  fields,
  submitLabel,
  footer,
}: AuthFormProps) {
  const [state, formAction, pending] = useActionState(
    async (_prevState: { error?: string } | null, formData: FormData) => {
      return await action(formData);
    },
    null
  );

  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-auth-card)] p-8 shadow-sm sm:p-10">
      <div className="mb-8">
        <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-[var(--color-text-primary)]">
          {title}
        </h1>
        <p className="mt-2 text-[15px] text-[var(--color-text-secondary)]">
          {subtitle}
        </p>
      </div>

      <form action={formAction} className="space-y-5">
        {state?.error && <ErrorMessage>{state.error}</ErrorMessage>}

        {fields.map((field) => (
          <Input
            key={field.name}
            name={field.name}
            label={field.label}
            type={field.type ?? "text"}
            placeholder={field.placeholder}
            required={field.required}
            autoComplete={field.autoComplete}
          />
        ))}

        <Button
          type="submit"
          size="lg"
          className="mt-2 w-full"
          disabled={pending}
        >
          {pending && <Loader2 className="h-4 w-4 animate-spin" />}
          {submitLabel}
        </Button>
      </form>

      <div className="mt-8 text-center text-sm text-[var(--color-text-secondary)]">
        {footer}
      </div>
    </div>
  );
}
